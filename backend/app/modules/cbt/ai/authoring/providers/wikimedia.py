"""Wikimedia Commons image-search provider for CBT AI authoring."""

from __future__ import annotations

import html
import re
from typing import Any, Mapping
from urllib.parse import quote, urlparse

import httpx

from app.modules.cbt.ai.authoring.flow_logging import get_question_generation_logger
from app.modules.cbt.ai.authoring.providers.base import BaseImageSearchProvider, ImageCandidate

logger = get_question_generation_logger("wikimedia")


class WikimediaProviderError(RuntimeError):
    """Raised when Wikimedia Commons cannot successfully complete a request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WikimediaCommonsImageSearchProvider(BaseImageSearchProvider):
    """Search Wikimedia Commons for freely reusable educational images."""

    provider_name = "wikimedia_commons"
    DEFAULT_API_URL = "https://commons.wikimedia.org/w/api.php"
    DEFAULT_TIMEOUT_SECONDS = 15.0
    DEFAULT_USER_AGENT = "WEAVE-CBT-Bot/1.0 (+https://weavecloudspace.com)"
    FILE_NAMESPACE = 6
    MAX_SEARCH_RESULTS = 50
    THUMBNAIL_WIDTH = 1600

    def __init__(
        self,
        *,
        api_url: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.api_url = (api_url or self.DEFAULT_API_URL).strip()
        self.timeout = timeout or self.DEFAULT_TIMEOUT_SECONDS
        self.user_agent = (user_agent or self.DEFAULT_USER_AGENT).strip()

    def is_configured(self) -> bool:
        return bool(self.api_url and self.user_agent)

    async def search(
        self,
        *,
        query: str,
        limit: int = 10,
        metadata: Mapping[str, Any] | None = None,
    ) -> list[ImageCandidate]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Wikimedia Commons search query cannot be empty")
        if len(normalized_query) > 300:
            raise ValueError("Wikimedia Commons search query cannot exceed 300 characters")
        if type(limit) is not int or limit <= 0:
            raise ValueError("Wikimedia Commons search limit must be a positive integer")

        metadata = dict(metadata or {})
        params = self._build_search_params(query=normalized_query, limit=limit)
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        logger.info(
            "cbt.ai.wikimedia.search.started",
            extra={
                "wikimedia_query": normalized_query,
                "wikimedia_limit": limit,
                "wikimedia_requested_result_count": params["gsrlimit"],
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.api_url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning(
                "cbt.ai.wikimedia.search.failed",
                extra={
                    "wikimedia_query": normalized_query,
                    "wikimedia_error_type": type(exc).__name__,
                    "wikimedia_error_message": str(exc),
                },
            )
            raise WikimediaProviderError("Wikimedia Commons image search timed out.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "cbt.ai.wikimedia.search.failed",
                extra={
                    "wikimedia_query": normalized_query,
                    "wikimedia_error_type": type(exc).__name__,
                    "wikimedia_error_message": str(exc),
                },
            )
            raise WikimediaProviderError("Unable to connect to Wikimedia Commons.") from exc

        if response.is_error:
            retry_after = response.headers.get("Retry-After")
            logger.warning(
                "cbt.ai.wikimedia.search.failed",
                extra={
                    "wikimedia_query": normalized_query,
                    "wikimedia_status_code": response.status_code,
                    "wikimedia_retry_after": retry_after,
                },
            )
            raise WikimediaProviderError(
                f"Wikimedia Commons image search failed with HTTP {response.status_code}.",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise WikimediaProviderError(
                "Wikimedia Commons returned an invalid JSON response."
            ) from exc

        if not isinstance(payload, dict):
            raise WikimediaProviderError(
                "Wikimedia Commons returned an unexpected response structure."
            )

        query_payload = payload.get("query")
        pages = query_payload.get("pages") if isinstance(query_payload, dict) else None
        if pages is None:
            pages = []
        if not isinstance(pages, list):
            raise WikimediaProviderError(
                "Wikimedia Commons response does not contain a valid pages list."
            )

        candidates: list[ImageCandidate] = []
        filtered_count = 0
        for page in pages:
            if not isinstance(page, dict):
                filtered_count += 1
                continue
            candidate = self._normalize_candidate(page, metadata=metadata)
            if candidate is None:
                filtered_count += 1
                continue
            candidates.append(candidate)
            if len(candidates) >= limit:
                break

        logger.info(
            "cbt.ai.wikimedia.search.completed",
            extra={
                "wikimedia_query": normalized_query,
                "wikimedia_raw_result_count": len(pages),
                "wikimedia_candidate_count": len(candidates),
                "wikimedia_filtered_result_count": filtered_count,
            },
        )
        return candidates

    def _build_search_params(self, *, query: str, limit: int) -> dict[str, str | int]:
        requested = min(max(limit * 2, 10), self.MAX_SEARCH_RESULTS)
        return {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": self.FILE_NAMESPACE,
            "gsrwhat": "text",
            "gsrsort": "relevance",
            "gsrlimit": requested,
            "prop": "imageinfo|info",
            "inprop": "url",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": self.THUMBNAIL_WIDTH,
            "redirects": "1",
        }

    def _normalize_candidate(
        self,
        page: Mapping[str, Any],
        *,
        metadata: Mapping[str, Any],
    ) -> ImageCandidate | None:
        image_info_list = page.get("imageinfo")
        if not isinstance(image_info_list, list) or not image_info_list:
            return self._reject_candidate(page, "missing_imageinfo")
        image_info = image_info_list[0]
        if not isinstance(image_info, dict):
            return self._reject_candidate(page, "invalid_imageinfo")

        extmetadata = image_info.get("extmetadata")
        if not isinstance(extmetadata, dict):
            extmetadata = {}

        license_name = self._metadata_value(extmetadata, "LicenseShortName") or self._metadata_value(
            extmetadata, "UsageTerms"
        )
        if not license_name:
            return self._reject_candidate(page, "missing_license")
        if not self._license_allows_commercial_reuse(license_name):
            return self._reject_candidate(
                page,
                "license_not_commercially_reusable",
                wikimedia_license_name=license_name,
            )

        source_url = self._clean_url(page.get("canonicalurl") or page.get("fullurl"))
        title = self._clean_string(page.get("title"))
        if source_url is None and title:
            source_url = self._build_source_url(title)
        if source_url is None:
            return self._reject_candidate(page, "missing_source_url")

        original_url = self._clean_url(image_info.get("url"))
        thumbnail_url = self._clean_url(image_info.get("thumburl"))
        image_url = thumbnail_url or original_url
        if image_url is None:
            return self._reject_candidate(page, "missing_image_url")

        width = self._positive_int(image_info.get("thumbwidth")) or self._positive_int(
            image_info.get("width")
        )
        height = self._positive_int(image_info.get("thumbheight")) or self._positive_int(
            image_info.get("height")
        )

        min_width = self._positive_int(metadata.get("min_width"))
        min_height = self._positive_int(metadata.get("min_height"))
        if min_width is not None and (width is None or width < min_width):
            return self._reject_candidate(page, "below_min_width")
        if min_height is not None and (height is None or height < min_height):
            return self._reject_candidate(page, "below_min_height")

        original_mime = self._clean_string(image_info.get("mime"))
        mime_type = original_mime.casefold() if original_mime else None
        if thumbnail_url and mime_type == "image/svg+xml":
            mime_type = "image/png"

        allowed_mime_types = metadata.get("allowed_mime_types")
        if isinstance(allowed_mime_types, str):
            allowed_mime_types = {allowed_mime_types}
        if allowed_mime_types and (mime_type is None or mime_type not in allowed_mime_types):
            return self._reject_candidate(page, "disallowed_mime_type")

        display_title = title.removeprefix("File:").strip() if title else None
        creator = self._clean_markup(self._metadata_value(extmetadata, "Artist"))
        attribution = self._clean_markup(
            self._metadata_value(extmetadata, "Credit")
            or self._metadata_value(extmetadata, "Attribution")
        )
        license_url = self._clean_url(self._metadata_value(extmetadata, "LicenseUrl"))

        page_id = page.get("pageid")
        external_id = str(page_id) if type(page_id) is int and page_id > 0 else display_title

        return ImageCandidate(
            source=self.provider_name,
            source_url=source_url,
            external_id=external_id,
            title=display_title,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            creator=creator,
            attribution_text=attribution,
            license_name=license_name,
            license_url=license_url,
            width=width,
            height=height,
            mime_type=mime_type,
        )

    @classmethod
    def _reject_candidate(
        cls,
        page: Mapping[str, Any],
        reason: str,
        **details: Any,
    ) -> None:
        logger.debug(
            "cbt.ai.wikimedia.result.filtered",
            extra={
                "wikimedia_filter_reason": reason,
                "wikimedia_page_id": page.get("pageid"),
                "wikimedia_title": cls._clean_string(page.get("title")),
                **details,
            },
        )
        return None

    @staticmethod
    def _metadata_value(metadata: Mapping[str, Any], key: str) -> str | None:
        item = metadata.get(key)
        if not isinstance(item, dict):
            return None
        value = item.get("value")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _license_allows_commercial_reuse(license_name: str) -> bool:
        normalized = re.sub(r"\s+", " ", license_name).strip().casefold()
        if any(
            marker in normalized
            for marker in (
                "noncommercial",
                "non-commercial",
                "by-nc",
                "by nc",
                "no derivatives",
                "no-derivatives",
                "by-nd",
                "by nd",
            )
        ):
            return False
        return any(
            marker in normalized
            for marker in (
                "public domain",
                "cc0",
                "cc by",
                "cc-by",
                "attribution",
                "gfdl",
                "gnu free documentation",
                "free art license",
            )
        )

    @staticmethod
    def _clean_markup(value: str | None) -> str | None:
        if not value:
            return None
        without_tags = re.sub(r"<[^>]+>", " ", value)
        cleaned = " ".join(html.unescape(without_tags).split())
        return cleaned or None

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @classmethod
    def _clean_url(cls, value: Any) -> str | None:
        value = cls._clean_string(value)
        if value is None:
            return None
        try:
            parsed = urlparse(value)
            if not parsed.hostname or parsed.username or parsed.password:
                return None
            parsed.port
        except ValueError:
            return None
        if parsed.scheme != "https" or not parsed.netloc:
            return None
        return value

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        if type(value) is int and value > 0:
            return value
        return None

    @staticmethod
    def _build_source_url(title: str) -> str:
        normalized_title = title.replace(" ", "_")
        return "https://commons.wikimedia.org/wiki/" + quote(normalized_title, safe="():,_-")
