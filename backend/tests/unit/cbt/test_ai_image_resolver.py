from __future__ import annotations

import pytest

from app.modules.cbt.ai.image_resolver import ImageResolver, ImageResolverError
from app.modules.cbt.ai.providers.base import (
    ImageCandidate,
    ProviderGeneratedImage,
    ProviderImageEvaluationResult,
    ProviderImageGenerationResult,
)


class FakeSearchProvider:
    provider_name = "fake-search"

    def __init__(self, candidates: list[ImageCandidate]) -> None:
        self.candidates = candidates
        self.last_limit: int | None = None

    def is_configured(self) -> bool:
        return True

    async def search(self, *, query: str, limit: int = 10, metadata=None):
        self.last_limit = limit
        return self.candidates[:limit]


class FakeEvaluationProvider:
    provider_name = "fake-evaluator"

    def __init__(self, result: ProviderImageEvaluationResult) -> None:
        self.result = result
        self.received_candidates: list[ImageCandidate] = []
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    async def evaluate_images(self, *, requirement: str, candidates):
        self.calls += 1
        self.received_candidates = list(candidates)
        return self.result


class FakeGenerationProvider:
    provider_name = "fake-generator"

    def __init__(self) -> None:
        self.calls = 0
        self.last_prompt: str | None = None

    def is_configured(self) -> bool:
        return True

    async def generate_image(
        self,
        *,
        prompt: str,
        metadata=None,
        reference_images=None,
    ) -> ProviderImageGenerationResult:
        self.calls += 1
        self.last_prompt = prompt
        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type="image/png",
                data_base64="generated-image",
            )
        )


def _candidate(index: int) -> ImageCandidate:
    return ImageCandidate(
        source="openverse",
        source_url=f"https://example.com/source/{index}",
        image_url=f"https://example.com/image/{index}.jpg",
        thumbnail_url=f"https://example.com/thumb/{index}.jpg",
    )


@pytest.mark.asyncio
async def test_resolver_preserves_search_ranking_and_reviews_only_top_three() -> None:
    candidates = [_candidate(index) for index in range(6)]
    search = FakeSearchProvider(candidates)
    evaluator = FakeEvaluationProvider(
        ProviderImageEvaluationResult(
            decision="use_candidate",
            selected_index=1,
        )
    )
    generator = FakeGenerationProvider()

    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=evaluator,
        generation_provider=generator,
    )

    result = await resolver.resolve(
        requirement="A clear photograph of a hibiscus flower",
        search_query="hibiscus flower close up",
    )

    assert search.last_limit == 10
    assert evaluator.received_candidates == candidates[:3]
    assert result.source == "search"
    assert result.candidate is candidates[1]
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_resolver_generates_when_evaluator_rejects_search_results() -> None:
    search = FakeSearchProvider([_candidate(0), _candidate(1)])
    evaluator = FakeEvaluationProvider(
        ProviderImageEvaluationResult(
            decision="generate_image",
            reason="None matches the required diagram.",
        )
    )
    generator = FakeGenerationProvider()

    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=evaluator,
        generation_provider=generator,
    )

    result = await resolver.resolve(
        requirement="An unlabeled plant-cell diagram with arrow X on the nucleus",
        search_query="plant cell educational diagram",
        generation_prompt="Generate an unlabeled plant-cell diagram with arrow X on the nucleus",
    )

    assert result.source == "generated"
    assert result.generation is not None
    assert result.evaluation is evaluator.result
    assert generator.calls == 1


@pytest.mark.asyncio
async def test_resolver_generates_immediately_when_search_returns_nothing() -> None:
    search = FakeSearchProvider([])
    evaluator = FakeEvaluationProvider(
        ProviderImageEvaluationResult(decision="generate_image")
    )
    generator = FakeGenerationProvider()

    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=evaluator,
        generation_provider=generator,
    )

    result = await resolver.resolve(
        requirement="A photograph of a hibiscus flower",
        search_query="hibiscus flower",
    )

    assert result.source == "generated"
    assert evaluator.calls == 0
    assert generator.calls == 1
    assert generator.last_prompt == "A photograph of a hibiscus flower"


@pytest.mark.asyncio
async def test_resolver_rejects_invalid_selected_candidate_index() -> None:
    search = FakeSearchProvider([_candidate(0)])
    evaluator = FakeEvaluationProvider(
        ProviderImageEvaluationResult(
            decision="use_candidate",
            selected_index=4,
        )
    )
    generator = FakeGenerationProvider()

    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=evaluator,
        generation_provider=generator,
    )

    with pytest.raises(ImageResolverError):
        await resolver.resolve(
            requirement="A hibiscus flower",
            search_query="hibiscus flower",
        )
