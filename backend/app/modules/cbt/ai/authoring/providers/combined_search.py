"""Concurrent multi-source image search for CBT AI authoring."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse

from app.modules.cbt.ai.authoring.flow_logging import get_question_generation_logger
from app.modules.cbt.ai.authoring.providers.base import BaseImageSearchProvider, ImageCandidate

logger = get_question_generation_logger("combined_search")


class CombinedImageSearchProviderError(RuntimeError):
    """Raised when every configured image-search source fails."""


class CombinedImageSearchProvider(BaseImageSearchProvider):
    """Search multiple free image sources concurrently and merge their results."""

    provider_name = "combined"

    def __init__(self, providers: Sequence[BaseImageSearchProvider]) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("Combined image search requires at least one provider.")

    def is_configured(self) -> bool:
        return any(provider.is_configured() for provider in self.providers)

    async def search(
        self,
        *,
        query: str,
        limit: int = 10,
        metadata: Mapping[str, Any] | None = None,
    ) -> list[ImageCandidate]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Combined image search query cannot be empty")
        if type(limit) is not int or limit <= 0:
            raise ValueError("Combined image search limit must be a positive integer")

        active_providers = [provider for provider in self.providers if provider.is_configured()]
        if not active_providers:
            raise CombinedImageSearchProviderError("No image-search provider is configured.")

        logger.info(
            "cbt.ai.combined_search.started",
            extra={
                "image_search_query": normalized_query,
                "image_search_limit": limit,
                "image_search_sources": [
                    self._provider_name(provider) for provider in active_providers
                ],
                "image_search_source_count": len(active_providers),
            },
        )

        results = await asyncio.gather(
            *(
                provider.search(
                    query=normalized_query,
                    limit=limit,
                    metadata=metadata,
                )
                for provider in active_providers
            ),
            return_exceptions=True,
        )

        successful_groups: list[list[ImageCandidate]] = []
        failures: list[BaseException] = []
        per_source_counts: dict[str, int] = {}

        for provider, result in zip(active_providers, results, strict=True):
            source_name = self._provider_name(provider)
            if isinstance(result, BaseException):
                failures.append(result)
                logger.warning(
                    "cbt.ai.combined_search.source_failed",
                    extra={
                        "image_search_query": normalized_query,
                        "image_search_source": source_name,
                        "image_error_type": type(result).__name__,
                        "image_error_message": str(result),
                    },
                )
                continue

            successful_groups.append(result)
            per_source_counts[source_name] = len(result)

        if not successful_groups:
            raise CombinedImageSearchProviderError(
                "Every configured image-search source failed."
            ) from (failures[0] if failures else None)

        merged = self._interleave_and_dedupe(successful_groups, limit=limit)
        logger.info(
            "cbt.ai.combined_search.completed",
            extra={
                "image_search_query": normalized_query,
                "image_search_limit": limit,
                "image_search_source_result_counts": per_source_counts,
                "image_search_failed_source_count": len(failures),
                "image_search_merged_candidate_count": len(merged),
                "image_search_merged_sources": sorted({candidate.source for candidate in merged}),
            },
        )
        return merged

    @classmethod
    def _interleave_and_dedupe(
        cls,
        groups: Sequence[Sequence[ImageCandidate]],
        *,
        limit: int,
    ) -> list[ImageCandidate]:
        """Round-robin sources so one provider cannot crowd out the other."""

        cursors = [0 for _ in groups]
        merged: list[ImageCandidate] = []
        seen: set[tuple[str, str]] = set()

        while len(merged) < limit:
            progressed = False
            for group_index, group in enumerate(groups):
                while cursors[group_index] < len(group):
                    candidate = group[cursors[group_index]]
                    cursors[group_index] += 1
                    progressed = True
                    identity = cls._candidate_identity(candidate)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    merged.append(candidate)
                    break

                if len(merged) >= limit:
                    break

            if not progressed:
                break

        return merged

    @classmethod
    def _candidate_identity(cls, candidate: ImageCandidate) -> tuple[str, str]:
        """Prefer canonical source pages so Openverse/Commons overlaps collapse."""

        normalized_source_url = cls._normalize_url(candidate.source_url)
        if normalized_source_url:
            return ("source_url", normalized_source_url)

        normalized_image_url = cls._normalize_url(candidate.image_url)
        if normalized_image_url:
            return ("image_url", normalized_image_url)

        if candidate.external_id:
            return (
                "external_id",
                f"{candidate.source.casefold()}:{candidate.external_id.casefold()}",
            )

        return (
            "fallback",
            f"{candidate.source.casefold()}:{(candidate.title or '').strip().casefold()}",
        )

    @staticmethod
    def _normalize_url(value: str | None) -> str | None:
        if not value:
            return None
        try:
            parsed = urlparse(value.strip())
        except ValueError:
            return None
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        path = unquote(parsed.path).rstrip("/").casefold()
        return f"{parsed.hostname.casefold()}{path}"

    @staticmethod
    def _provider_name(provider: object) -> str:
        name = getattr(provider, "provider_name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        return type(provider).__name__
