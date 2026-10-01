"""Thumbnail-first materialization for CBT image candidate review."""

from __future__ import annotations

from dataclasses import replace

from app.modules.cbt.ai.authoring.image_materializer import ImageMaterializer
from app.modules.cbt.ai.authoring.providers.base import ImageCandidate, ProviderImageInput


class PreviewImageMaterializer(ImageMaterializer):
    """Use cheap candidate thumbnails for visual review before full download."""

    async def materialize_candidate_preview(
        self,
        candidate: ImageCandidate,
        *,
        label: str | None = None,
    ) -> ProviderImageInput:
        """Prefer a provider thumbnail, falling back to the normal image URL.

        The selected candidate is materialized again through materialize_candidate()
        after evaluation so final CBT output still gets the best available version.
        """

        primary_url = candidate.thumbnail_url or candidate.image_url
        fallback_url = (
            candidate.image_url
            if candidate.thumbnail_url
            and candidate.image_url
            and candidate.image_url != candidate.thumbnail_url
            else None
        )

        preview_candidate = replace(
            candidate,
            image_url=primary_url,
            thumbnail_url=fallback_url,
        )
        return await super().materialize_candidate(preview_candidate, label=label)
