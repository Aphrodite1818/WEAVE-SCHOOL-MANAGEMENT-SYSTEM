from __future__ import annotations

import asyncio

import httpx
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

    def __init__(self, candidates, *, results_by_query=None):
        self.candidates = candidates
        self.results_by_query = dict(results_by_query or {})
        self.queries = []

    def is_configured(self):
        return True

    async def search(self, **kwargs):
        query = kwargs["query"]
        self.queries.append(query)
        return self.results_by_query.get(query, self.candidates)


class FakeEvaluator:
    provider_name = "eval"

    def __init__(self, decision="use_candidate", selected_index=0):
        self.decision = decision
        self.selected_index = selected_index
        self.images = None
        self.calls = 0

    def is_configured(self):
        return True

    async def evaluate_images(self, *, requirement, images):
        self.calls += 1
        self.images = list(images)
        return ProviderImageEvaluationResult(
            decision=self.decision,
            selected_index=self.selected_index if self.decision == "use_candidate" else None,
        )


class TransientThenSuccessfulEvaluator(FakeEvaluator):
    async def evaluate_images(self, *, requirement, images):
        self.calls += 1
        self.images = list(images)
        if self.calls == 1:
            try:
                raise httpx.RemoteProtocolError("server disconnected")
            except httpx.RemoteProtocolError as exc:
                raise RuntimeError("provider connection failed") from exc
        return ProviderImageEvaluationResult(
            decision="use_candidate",
            selected_index=0,
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


class ConcurrentTrackingMaterializer(FakeMaterializer):
    def __init__(self):
        super().__init__()
        self.active = 0
        self.max_active = 0

    async def materialize_candidate(self, candidate, *, label=None):
        self.candidate_calls.append(candidate.source)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return _binary(candidate.source)
        finally:
            self.active -= 1


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
async def test_zero_result_search_retries_once_with_broader_keywords() -> None:
    candidate = ImageCandidate(
        source="tree-rings",
        source_url="https://example.com/tree-rings-source",
        image_url="https://example.com/tree-rings.png",
    )
    original_query = "tree trunk cross section annual rings biology diagram"
    broader_query = "tree ring"
    search = FakeSearchProvider(
        [],
        results_by_query={
            original_query: [],
            broader_query: [candidate],
        },
    )
    evaluator = FakeEvaluator()
    generator = FakeGenerationProvider()
    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=evaluator,
        generation_provider=generator,
        materializer=FakeMaterializer(),
    )

    result = await resolver.resolve(
        requirement="A tree trunk cross-section showing annual rings",
        search_query=original_query,
    )

    assert search.queries == [original_query, broader_query]
    assert result.source == "search"
    assert result.candidate is candidate
    assert result.image.label == "tree-rings"
    assert [image.label for image in evaluator.images] == ["tree-rings"]
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_candidate_metadata_ranking_prioritizes_relevant_titles() -> None:
    candidates = [
        ImageCandidate(
            source="apollo",
            source_url="https://example.com/apollo",
            image_url="https://example.com/apollo.jpg",
            title="Apollo Fuel Cell Number 1",
        ),
        ImageCandidate(
            source="xylem",
            source_url="https://example.com/xylem",
            image_url="https://example.com/xylem.jpg",
            title="Xylem cells",
        ),
        ImageCandidate(
            source="plant-wall",
            source_url="https://example.com/plant-wall",
            image_url="https://example.com/plant-wall.jpg",
            title="Plant cell wall diagram",
        ),
        ImageCandidate(
            source="simple-plant-cell",
            source_url="https://example.com/simple-plant-cell",
            image_url="https://example.com/simple-plant-cell.jpg",
            title="Simple diagram of plant cell",
        ),
    ]
    materializer = FakeMaterializer()
    evaluator = FakeEvaluator(selected_index=0)
    resolver = ImageResolver(
        search_provider=FakeSearchProvider(candidates),
        evaluation_provider=evaluator,
        generation_provider=FakeGenerationProvider(),
        materializer=materializer,
        review_limit=2,
    )

    result = await resolver.resolve(
        requirement="A labeled diagram of a plant cell highlighting the cell wall",
        search_query="plant cell diagram",
    )

    assert materializer.candidate_calls == ["plant-wall", "simple-plant-cell"]
    assert [image.label for image in evaluator.images] == [
        "plant-wall",
        "simple-plant-cell",
    ]
    assert result.candidate is candidates[2]


@pytest.mark.asyncio
async def test_candidate_materialization_runs_with_bounded_concurrency() -> None:
    candidates = [
        ImageCandidate(
            source=f"candidate-{index}",
            source_url=f"https://example.com/source/{index}",
            image_url=f"https://example.com/image/{index}.jpg",
            title=f"Plant cell diagram {index}",
        )
        for index in range(6)
    ]
    materializer = ConcurrentTrackingMaterializer()
    resolver = ImageResolver(
        search_provider=FakeSearchProvider(candidates),
        evaluation_provider=FakeEvaluator(),
        generation_provider=FakeGenerationProvider(),
        materializer=materializer,
        review_limit=3,
    )

    result = await resolver.resolve(
        requirement="A plant cell diagram",
        search_query="plant cell diagram",
    )

    assert result.source == "search"
    assert materializer.max_active == 3
    assert len(materializer.candidate_calls) == 3


@pytest.mark.asyncio
async def test_transient_evaluation_network_failure_is_retried_once() -> None:
    candidate = ImageCandidate(
        source="plant-cell",
        source_url="https://example.com/plant-cell",
        image_url="https://example.com/plant-cell.png",
        title="Plant cell diagram",
    )
    evaluator = TransientThenSuccessfulEvaluator()
    generator = FakeGenerationProvider()
    resolver = ImageResolver(
        search_provider=FakeSearchProvider([candidate]),
        evaluation_provider=evaluator,
        generation_provider=generator,
        materializer=FakeMaterializer(),
    )
    resolver.EVALUATION_RETRY_DELAY_SECONDS = 0

    result = await resolver.resolve(
        requirement="A plant cell diagram",
        search_query="plant cell diagram",
    )

    assert result.source == "search"
    assert evaluator.calls == 2
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
