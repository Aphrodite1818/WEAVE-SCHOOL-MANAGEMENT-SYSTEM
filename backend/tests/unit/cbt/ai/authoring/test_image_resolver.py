from __future__ import annotations

import pytest

from app.modules.cbt.ai.authoring.image_materializer import ImageMaterializationError
from app.modules.cbt.ai.authoring.image_resolver import ImageResolver, ImageResolverError
from app.modules.cbt.ai.authoring.providers.base import (
    ImageCandidate,
    ProviderGeneratedImage,
    ProviderImageEvaluationResult,
    ProviderImageGenerationResult,
    ProviderImageInput,
    ProviderUsage,
)


def _binary(label: str) -> ProviderImageInput:
    return ProviderImageInput(
        data=f"image-{label}".encode(),
        content_type="image/png",
        sha256="0" * 64,
        width=100,
        height=80,
        label=label,
    )


class FakeSearchProvider:
    provider_name = "search"

    def __init__(self, candidates):
        self.candidates = candidates

    def is_configured(self):
        return True

    async def search(self, **kwargs):
        return self.candidates


class FakeEvaluator:
    provider_name = "eval"

    def __init__(self, decision="use_candidate", selected_index=0):
        self.decision = decision
        self.selected_index = selected_index
        self.images = None

    def is_configured(self):
        return True

    async def evaluate_images(self, *, requirement, images):
        self.images = list(images)
        return ProviderImageEvaluationResult(
            decision=self.decision,
            selected_index=self.selected_index if self.decision == "use_candidate" else None,
        )


class FakeGenerationProvider:
    provider_name = "generation"

    def __init__(self):
        self.calls = 0

    def is_configured(self):
        return True

    async def generate_image(self, **kwargs):
        self.calls += 1
        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type="image/png",
                data_base64=f"attempt-{self.calls}",
            ),
            usage=ProviderUsage(input_tokens=self.calls),
        )


class FakeMaterializer:
    def __init__(self, *, failing_sources=(), generated_failures_before_success=0):
        self.failing_sources = set(failing_sources)
        self.generated_failures_before_success = generated_failures_before_success
        self.candidate_calls = []
        self.generated_calls = 0

    async def materialize_candidate(self, candidate, *, label=None):
        self.candidate_calls.append(candidate.source)
        if candidate.source in self.failing_sources:
            raise ImageMaterializationError("cannot download")
        return _binary(candidate.source)

    async def materialize_generated(self, image, *, label=None):
        self.generated_calls += 1
        if self.generated_calls <= self.generated_failures_before_success:
            raise ImageMaterializationError("generated image cannot be materialized")
        return _binary("generated")


@pytest.mark.asyncio
async def test_unmaterializable_search_candidate_is_removed_before_evaluation() -> None:
    first = ImageCandidate(
        source="broken",
        source_url="https://example.com/broken-source",
        image_url="https://example.com/broken.png",
    )
    second = ImageCandidate(
        source="usable",
        source_url="https://example.com/usable-source",
        image_url="https://example.com/usable.png",
    )
    evaluator = FakeEvaluator()
    generator = FakeGenerationProvider()
    materializer = FakeMaterializer(failing_sources={"broken"})
    resolver = ImageResolver(
        search_provider=FakeSearchProvider([first, second]),
        evaluation_provider=evaluator,
        generation_provider=generator,
        materializer=materializer,
    )

    result = await resolver.resolve(
        requirement="A useful diagram",
        search_query="useful diagram",
    )

    assert result.source == "search"
    assert result.candidate is second
    assert result.image.label == "usable"
    assert [image.label for image in evaluator.images] == ["usable"]
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_all_unusable_search_candidates_fall_back_to_generated_materialized_bytes() -> None:
    candidate = ImageCandidate(
        source="broken",
        source_url="https://example.com/source",
        image_url="https://example.com/broken.png",
    )
    evaluator = FakeEvaluator()
    generator = FakeGenerationProvider()
    materializer = FakeMaterializer(failing_sources={"broken"})
    resolver = ImageResolver(
        search_provider=FakeSearchProvider([candidate]),
        evaluation_provider=evaluator,
        generation_provider=generator,
        materializer=materializer,
    )

    result = await resolver.resolve(
        requirement="A useful diagram",
        search_query="useful diagram",
    )

    assert result.source == "generated"
    assert result.image.label == "generated"
    assert generator.calls == 1
    assert materializer.generated_calls == 1
    assert len(result.generation_attempts) == 1
    assert evaluator.images is None


@pytest.mark.asyncio
async def test_unusable_generated_payload_is_regenerated_once_before_succeeding() -> None:
    generator = FakeGenerationProvider()
    materializer = FakeMaterializer(generated_failures_before_success=1)
    resolver = ImageResolver(
        search_provider=FakeSearchProvider([]),
        evaluation_provider=FakeEvaluator(),
        generation_provider=generator,
        materializer=materializer,
    )

    result = await resolver.resolve(
        requirement="A useful diagram",
        search_query="useful diagram",
    )

    assert result.source == "generated"
    assert generator.calls == 2
    assert materializer.generated_calls == 2
    assert len(result.generation_attempts) == 2
    assert [attempt.usage.input_tokens for attempt in result.generation_attempts] == [1, 2]
    assert result.generation is result.generation_attempts[-1]


@pytest.mark.asyncio
async def test_unusable_generated_payload_fails_after_exactly_two_attempts() -> None:
    generator = FakeGenerationProvider()
    materializer = FakeMaterializer(generated_failures_before_success=2)
    resolver = ImageResolver(
        search_provider=FakeSearchProvider([]),
        evaluation_provider=FakeEvaluator(),
        generation_provider=generator,
        materializer=materializer,
    )

    with pytest.raises(ImageResolverError, match="after retry"):
        await resolver.resolve(
            requirement="A useful diagram",
            search_query="useful diagram",
        )

    assert generator.calls == 2
    assert materializer.generated_calls == 2
