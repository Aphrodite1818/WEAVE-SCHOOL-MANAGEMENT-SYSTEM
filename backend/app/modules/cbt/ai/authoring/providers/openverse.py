"""Openverse image-search provider for CBT AI question writing"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import secrets
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr
from redis.exceptions import RedisError

from app.config.settings import settings
from app.core.cache.redis import get_redis
from app.modules.cbt.ai.authoring.providers.base import BaseImageSearchProvider, ImageCandidate


# EXCEPTIONS


class OpenverseProviderError(RuntimeError):
    """Raised when Openverse cannot successfully complete a request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenverseProviderConfigurationError(OpenverseProviderError):
    """Raised when Openverse credentials are partially configured"""


# OPENVERSE PROVIDER


class OpenverseImageSearchProvider(BaseImageSearchProvider):
    """Search openly licensed images, sharing OAuth tokens through Redis."""

    provider_name = "openverse"
    TOKEN_CACHE_KEY = "cbt:ai:openverse:access_token"
    TOKEN_REFRESH_LOCK_KEY = "cbt:ai:openverse:access_token:lock"
    TOKEN_EXPIRY_BUFFER_SECONDS = 60
    LOCK_SAFETY_BUFFER_SECONDS = 5
    LOCK_POLL_INTERVAL_SECONDS = 0.25

    _RELEASE_LOCK_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    _CACHE_TOKEN_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        redis.call("set", KEYS[2], ARGV[2], "EX", ARGV[3])
        return 1
    end
    return 0
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: SecretStr | str | None = None,
        timeout: float | None = None,
    ) -> None:
        configured_client_id = client_id if client_id is not None else settings.OPENVERSE_CLIENT_ID

        configured_client_secret = (
            client_secret if client_secret is not None else settings.OPENVERSE_CLIENT_SECRET
        )

        if isinstance(configured_client_secret, SecretStr):
            configured_client_secret = configured_client_secret.get_secret_value()

        self.client_id = configured_client_id.strip() if configured_client_id else None

        self.client_secret = configured_client_secret.strip() if configured_client_secret else None

        self.base_url = (base_url or settings.OPENVERSE_BASE_URL).rstrip("/")

        self.timeout = timeout or settings.OPENVERSE_REQUEST_TIMEOUT_SECONDS
        # Tokens are application credentials, not tenant data. Scope by endpoint
        # and credentials, including rotations, without exposing secrets in keys.
        cache_scope = hashlib.sha256(
            json.dumps([self.base_url, self.client_id, self.client_secret]).encode()
        ).hexdigest()
        self._token_cache_key = f"{self.TOKEN_CACHE_KEY}:{cache_scope}"
        self._token_lock_key = f"{self.TOKEN_REFRESH_LOCK_KEY}:{cache_scope}"

    # configuration
    def is_configured(self) -> bool:
        """
        Openverse can operate anonymously.

        Therefore the provider itself is always usable when
        OAuth credentials have not been configured
        """

        return not self._has_partial_credentials()

    def _has_complete_credentials(self) -> bool:
        """Return whether both OAuth credentials are configured"""

        return bool(self.client_id and self.client_secret)

    def _has_partial_credentials(self) -> bool:
        """Return whether only one OAuth credential is configured."""

        return bool(self.client_id) != bool(self.client_secret)

    # endpoints

    def _build_search_url(self) -> str:
        """Build the Openverse image-search endpoint"""

        return f"{self.base_url}/images/"

    def _build_token_url(self) -> str:
        """Build the Openverse OAuth token endpoint"""

        return f"{self.base_url}/auth_tokens/token/"

    # Authentication

    async def _get_headers(self) -> dict[str, str]:
        """Build request headers

        Anonymous requests are allowed when no credentials are present
        """

        headers = {"Accept": "application/json"}

        if self._has_partial_credentials():
            raise OpenverseProviderConfigurationError(
                "Openverse client ID and client secret must either both be configured or omitted"
            )

        if not self._has_complete_credentials():
            return headers

        access_token = await self._get_access_token()

        headers["Authorization"] = f"Bearer {access_token}"

        return headers

    async def _get_access_token(self) -> str:
        """Read or refresh a shared token using a bounded, owner-checked lock."""
        redis = get_redis()
        if redis is None:
            raise OpenverseProviderError(
                "Shared Redis is unavailable for Openverse token management"
            )

        lock_seconds = math.ceil(self.timeout + self.LOCK_SAFETY_BUFFER_SECONDS)
        owner = secrets.token_hex(16)
        try:
            async with asyncio.timeout(lock_seconds):
                while True:
                    cached_token = await redis.get(self._token_cache_key)
                    if cached_token:
                        return cached_token
                    acquired = await redis.set(
                        self._token_lock_key, owner, nx=True, ex=lock_seconds
                    )
                    if acquired:
                        try:
                            # Another worker may have published between our GET and SET.
                            cached_token = await redis.get(self._token_cache_key)
                            if cached_token:
                                return cached_token
                            started_at = time.monotonic()
                            token, expires_in = await self._request_access_token()
                            buffer = min(self.TOKEN_EXPIRY_BUFFER_SECONDS, expires_in // 10)
                            ttl = math.floor(expires_in - buffer - (time.monotonic() - started_at))
                            if ttl <= 0:
                                raise OpenverseProviderError(
                                    "Openverse token expired before it could be cached."
                                )
                            stored = await redis.eval(
                                self._CACHE_TOKEN_SCRIPT,
                                2,
                                self._token_lock_key,
                                self._token_cache_key,
                                owner,
                                token,
                                ttl,
                            )
                            if not stored:
                                raise OpenverseProviderError(
                                    "Openverse token refresh lock expired."
                                )
                            return token
                        finally:
                            # A stale worker must never remove a successor's lock.
                            # On Redis failure the lock still expires automatically.
                            try:
                                await redis.eval(
                                    self._RELEASE_LOCK_SCRIPT, 1, self._token_lock_key, owner
                                )
                            except RedisError:
                                pass
                    await asyncio.sleep(self.LOCK_POLL_INTERVAL_SECONDS)
        except TimeoutError as exc:
            raise OpenverseProviderError("Openverse token refresh timed out.") from exc
        except RedisError as exc:
            raise OpenverseProviderError("Openverse token cache is unavailable.") from exc

    async def _request_access_token(self) -> tuple[str, int]:
        """Request an OAuth client-credentials token from Openverse"""

        if not self._has_complete_credentials():
            raise OpenverseProviderConfigurationError(
                "Openverse OAuth credentials are not configured"
            )

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_token_url(), data=payload, headers={"Accept": "application/json"}
                )

        except httpx.TimeoutException as exc:
            raise OpenverseProviderError("Openverse authentication request timed out.") from exc

        except httpx.RequestError as exc:
            raise OpenverseProviderError("Unable to connect to Openverse authentication.") from exc

        if response.is_error:
            raise OpenverseProviderError(
                (f"Openverse authentication failed with HTTP {response.status_code}."),
                status_code=response.status_code,
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise OpenverseProviderError("Openverse authentication returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise OpenverseProviderError(
                "Openverse authentication returned an unexpected response."
            )

        access_token = data.get("access_token")

        if not isinstance(access_token, str) or not access_token.strip():
            raise OpenverseProviderError("Openverse authentication returned no access token.")

        expires_in = data.get("expires_in")

        if type(expires_in) is not int or expires_in <= 0:
            raise OpenverseProviderError("Openverse returned an invalid token lifetime.")

        return access_token.strip(), expires_in

    # IMAGE SEARCH

    async def search(
        self, *, query: str, limit: int = 10, metadata: Mapping[str, Any] | None = None
    ) -> list[ImageCandidate]:
        """
        Search Openverse for suitable image candidates

        This provider only performs retrieval and basic structural
        filtering. It does NOT decide whether an image is semantically
        appropriate for a particular CBT question

        That decision belongs to the image resolver/orchestration layer
        """

        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("Openverse search query cannot be empty")

        if len(normalized_query) > 200:
            raise ValueError("Openverse search query cannot exceed 200 characters")

        if type(limit) is not int or limit <= 0:
            raise ValueError("Openverse search limit must be a positive integer")

        metadata = dict(metadata or {})

        headers = await self._get_headers()

        params = self._build_search_params(query=normalized_query, limit=limit, metadata=metadata)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_search_url(), headers=headers, params=params
                )

        except httpx.TimeoutException as exc:
            raise OpenverseProviderError("Openverse image search timed out.") from exc

        except httpx.RequestError as exc:
            raise OpenverseProviderError("Unable to connect to Openverse.") from exc

        if response.is_error:
            raise OpenverseProviderError(
                (f"Openverse image search failed with HTTP {response.status_code}."),
                status_code=response.status_code,
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise OpenverseProviderError("Openverse returned an invalid JSON response.") from exc

        if not isinstance(data, dict):
            raise OpenverseProviderError("Openverse returned an unexpected response structure.")

        results = data.get("results")

        if not isinstance(results, list):
            raise OpenverseProviderError(
                "Openverse response does not contain a valid results list."
            )

        candidates: list[ImageCandidate] = []

        for result in results:
            if not isinstance(result, dict):
                continue

            candidate = self._normalize_candidate(result, metadata=metadata)

            if candidate is None:
                continue

            candidates.append(candidate)

            if len(candidates) >= limit:
                break

        return candidates

    # SEARCH PARAMETERS

    def _build_search_params(
        self, *, query: str, limit: int, metadata: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Build Openverse image-search query parameters."""

        authenticated = self._has_complete_credentials()

        max_page_size = 50 if authenticated else 20

        # Request some extra candidates because local validation
        # may discard unusable results.
        requested_page_size = max(limit * 2, 10)

        page_size = min(requested_page_size, max_page_size)

        params: dict[str, Any] = {
            "q": query,
            "page_size": page_size,
            # We do not want mature material in educational CBT content.
            "mature": "false",
            # Ask Openverse to remove known dead links where possible.
            "filter_dead": "true",
            # Weave is commercial SaaS, so avoid licenses that explicitly
            # prohibit commercial use unless later policy says otherwise.
            "license_type": "commercial",
        }

        supported_filters = {
            "license",
            "license_type",
            "source",
            "excluded_source",
            "extension",
            "category",
            "aspect_ratio",
            "size",
        }

        for key in supported_filters:
            value = metadata.get(key)

            if value is None:
                continue

            normalized_value = self._normalize_filter_value(value)

            if normalized_value:
                params[key] = normalized_value

        return params

    @staticmethod
    def _normalize_filter_value(value: Any) -> str | None:
        """
        Normalize Openverse filters.

        Lists/tuples/sets become comma-separated query values.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        if isinstance(value, (list, tuple, set)):
            normalized_items = [str(item).strip() for item in value if str(item).strip()]

            if not normalized_items:
                return None

            return ",".join(normalized_items)

        return str(value).strip() or None

    # RESULT NORMALIZATION

    def _normalize_candidate(
        self, result: Mapping[str, Any], *, metadata: Mapping[str, Any]
    ) -> ImageCandidate | None:
        """
        Convert an Openverse result into an application-level
        ImageCandidate.

        Returns None when the result is obviously unusable.
        """

        image_url = self._clean_url(result.get("url"))

        if image_url is None:
            return None

        license_slug = self._clean_string(result.get("license"))

        if license_slug is None:
            return None

        mature = result.get("mature")

        if mature is True:
            return None

        width = self._positive_int(result.get("width"))

        height = self._positive_int(result.get("height"))

        min_width = self._positive_int(metadata.get("min_width"))

        min_height = self._positive_int(metadata.get("min_height"))

        if min_width is not None and (width is None or width < min_width):
            return None

        if min_height is not None and (height is None or height < min_height):
            return None

        mime_type = self._normalize_mime_type(result.get("filetype"))

        allowed_mime_types = metadata.get("allowed_mime_types")
        if isinstance(allowed_mime_types, str):
            allowed_mime_types = {allowed_mime_types}

        if allowed_mime_types and (mime_type is None or mime_type not in allowed_mime_types):
            return None

        source_url = self._clean_url(result.get("foreign_landing_url")) or self._clean_url(
            result.get("detail_url")
        )

        # We want a traceable source page for attribution and licensing.
        if source_url is None:
            return None

        source = (
            self._clean_string(result.get("source"))
            or self._clean_string(result.get("provider"))
            or "openverse"
        )

        license_version = self._clean_string(result.get("license_version"))

        license_name = self._format_license_name(license_slug, license_version)

        return ImageCandidate(
            source=source,
            source_url=source_url,
            external_id=self._clean_string(result.get("id")),
            title=self._clean_string(result.get("title")),
            image_url=image_url,
            thumbnail_url=self._clean_url(result.get("thumbnail")),
            creator=self._clean_string(result.get("creator")),
            attribution_text=self._clean_string(result.get("attribution")),
            license_name=license_name,
            license_url=self._clean_url(result.get("license_url")),
            width=width,
            height=height,
            mime_type=mime_type,
        )

    # NORMALIZATION HELPERS

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        """Return a normalized non-empty string."""

        if not isinstance(value, str):
            return None

        value = value.strip()

        return value or None

    @classmethod
    def _clean_url(cls, value: Any) -> str | None:
        """Return a valid HTTP/HTTPS URL or None."""

        value = cls._clean_string(value)

        if value is None:
            return None

        try:
            parsed = urlparse(value)
            if not parsed.hostname or parsed.username or parsed.password:
                return None
            parsed.port  # Validate malformed or out-of-range ports.
        except ValueError:
            return None

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        return value

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        """Return a positive integer or None."""

        if type(value) is int and value > 0:
            return value

        return None

    @staticmethod
    def _normalize_mime_type(filetype: Any) -> str | None:
        """
        Convert common Openverse file-type values into MIME types.

        Openverse notes that `filetype` is related to the file extension
        and is not guaranteed to be an exact MIME type.
        """

        if not isinstance(filetype, str):
            return None

        normalized = filetype.strip().lower()

        if not normalized:
            return None

        if normalized.startswith("image/"):
            return normalized

        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }

        return mime_types.get(normalized)

    @staticmethod
    def _format_license_name(license_slug: str, version: str | None) -> str:
        """Convert Openverse license slugs into readable license names."""

        license_names = {
            "by": "CC BY",
            "by-sa": "CC BY-SA",
            "by-nd": "CC BY-ND",
            "by-nc": "CC BY-NC",
            "by-nc-sa": "CC BY-NC-SA",
            "by-nc-nd": "CC BY-NC-ND",
            "cc0": "CC0",
            "pdm": "Public Domain Mark",
        }

        name = license_names.get(license_slug.lower(), license_slug.upper())

        if version:
            return f"{name} {version}"

        return name
