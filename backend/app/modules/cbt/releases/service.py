"""Resolve the latest WEAVE CBT installer metadata for this Weave environment."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import PurePath
import re
from time import monotonic
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.config.settings import EnvironmentType, settings
from app.modules.cbt.releases.schemas import CBTReleaseResponse

_RELEASE_REPOSITORY = "Aphrodite1818/WEAVE-CBT-MODULE"
_RELEASE_BASE_URL = f"https://github.com/{_RELEASE_REPOSITORY}/releases/download"
_RELEASE_TAGS = {
    "production": "manager-production-latest",
    "staging": "manager-staging-latest",
}
_IMAGE_REPOSITORY = "ghcr.io/aphrodite1818/weave-cbt-module"
_IMAGE_REFERENCE_PATTERN = re.compile(
    rf"^{re.escape(_IMAGE_REPOSITORY)}(?:"
    r":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"
    r"|@sha256:[0-9a-f]{64}"
    r")$"
)
_CACHE_TTL_SECONDS = 300.0


class CBTReleaseUnavailableError(RuntimeError):
    """Raised when the environment-specific installer metadata cannot be trusted."""


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    release: CBTReleaseResponse


class CBTReleaseService:
    """Fetch, validate and briefly cache the published installer manifest."""

    _cache: dict[str, _CacheEntry] = {}
    _lock = asyncio.Lock()

    @staticmethod
    def channel_for_environment() -> str:
        """Map Weave runtime environments onto public CBT installer channels."""

        if settings.ENV == EnvironmentType.PRODUCTION:
            return "production"
        return "staging"

    @classmethod
    async def get_latest(cls) -> CBTReleaseResponse:
        channel = cls.channel_for_environment()
        cached = cls._cache.get(channel)
        now = monotonic()
        if cached is not None and cached.expires_at > now:
            return cached.release

        async with cls._lock:
            cached = cls._cache.get(channel)
            now = monotonic()
            if cached is not None and cached.expires_at > now:
                return cached.release

            release = await cls._fetch_release(channel)
            cls._cache[channel] = _CacheEntry(
                expires_at=now + _CACHE_TTL_SECONDS,
                release=release,
            )
            return release

    @classmethod
    async def _fetch_release(cls, channel: str) -> CBTReleaseResponse:
        tag = _RELEASE_TAGS[channel]
        manifest_url = f"{_RELEASE_BASE_URL}/{tag}/release.json"

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(8.0, connect=4.0),
                headers={"Accept": "application/json", "User-Agent": "WEAVE-API"},
            ) as client:
                response = await client.get(manifest_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CBTReleaseUnavailableError(
                "The WEAVE CBT installer is temporarily unavailable. Please try again shortly."
            ) from exc

        if not isinstance(payload, dict):
            raise CBTReleaseUnavailableError(
                "The WEAVE CBT release manifest has an invalid structure."
            )

        try:
            release = CBTReleaseResponse.model_validate(payload)
        except ValidationError as exc:
            raise CBTReleaseUnavailableError(
                "The WEAVE CBT release manifest failed validation."
            ) from exc

        cls._validate_release(channel=channel, tag=tag, release=release)
        return release

    @staticmethod
    def _validate_release(
        *,
        channel: str,
        tag: str,
        release: CBTReleaseResponse,
    ) -> None:
        if release.channel != channel:
            raise CBTReleaseUnavailableError(
                "The published WEAVE CBT installer does not match this environment."
            )

        asset = release.installer_asset.strip()
        if not asset.lower().endswith(".exe") or PurePath(asset).name != asset or "\\" in asset:
            raise CBTReleaseUnavailableError("The WEAVE CBT installer asset name is invalid.")

        installer_url = str(release.installer_url)
        parsed = urlparse(installer_url)
        expected_prefix = f"/{_RELEASE_REPOSITORY}/releases/download/{tag}/"
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or not parsed.path.startswith(expected_prefix)
            or not parsed.path.endswith(f"/{asset}")
        ):
            raise CBTReleaseUnavailableError(
                "The WEAVE CBT installer URL failed release-channel validation."
            )

        if not _IMAGE_REFERENCE_PATTERN.fullmatch(release.image):
            raise CBTReleaseUnavailableError(
                "The WEAVE CBT release references an unexpected container image."
            )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the process-local manifest cache. Primarily useful for tests."""

        cls._cache.clear()
