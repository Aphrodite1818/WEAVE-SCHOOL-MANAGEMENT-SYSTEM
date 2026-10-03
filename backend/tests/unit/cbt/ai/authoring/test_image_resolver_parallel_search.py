from __future__ import annotations

import asyncio

import pytest

from app.modules.cbt.ai.authoring.image_materializer import ImageMaterializationError
from app.modules.cbt.ai.authoring.image_resolver import ImageResolver
from app.modules.cbt.ai.authoring.providers.base import (
    ImageCandidate,
    ProviderGeneratedImage,
    ProviderImageEvaluationResult,
    ProviderImageGenerationResult,
    ProviderImageInput,
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


class ParallelSearchProvider:
    provider_name = "search"

    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.queries: list[str] = []
        self.active = 0
        self.max_active = 0

    def is_configured(self):
        return True

    async def search(self, *, query, **kwargs):
        self.queries.append(query)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return list(self.results_by_query.get(query, []))
        finally:
            self.active -= 1


class RecordingMaterializer:
    def __init__(self, *, fail_candidates=False):
        self.fail_candidates = fail_candidates
        self.candidate_calls: list[str] = []

    async def materialize_candidate(self, candidate, *, label=None):
        self.candidate_calls.append(candidate.source)
        if self.fail_candidates:
            raise ImageMaterializationError("cannot download")
        return _binary(candidate.source)

    async def materialize_generated(self, image, *, label=None):
        return _binary("generated")


class Evaluator:
    provider_name = "eval"

    def __init__(self, selected_index=0):
        self.selected_index = selected_index
        self.images = []

    def is_configured(self):
        return True

    async def evaluate_images(self, *, requirement, images):
        self.images = list(images)
        return ProviderImageEvaluationResult(
            decision="use_candidate",
            selected_index=self.selected_index,
        )


class Generator:
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
                data_base64="unused-by-fake-materializer",
            )
        )


@pytest.mark.asyncio
async def test_primary_and_semantic_alternate_search_run_concurrently_and_dedupe() -> None:
    shared = ImageCandidate(
        source="helium",
        source_url="https://example.com/helium",
        external_id="shared-id",
        image_url="https://example.com/helium.png",
        title="Helium atom QM",
    )
    alternate_only = ImageCandidate(
        source="bohr",
        source_url="https://example.com/bohr",
        external_id="bohr-id",
        image_url="https://example.com/bohr.png",
        title="Atom electrons shells",
    )
    primary_query = "atom structure nucleus"
    alternate_query = "atom nucleus electron shell"
    search = ParallelSearchProvider(
        {
            primary_query: [shared],
            alternate_query: [shared, alternate_only],
        }
    )
    materializer = RecordingMaterializer()
    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=Evaluator(),
        generation_provider=Generator(),
        materializer=materializer,
        review_limit=2,
    )

    result = await resolver.resolve(
        requirement=(
            "A diagram of an atom showing the central nucleus containing protons "
            "and neutrons, surrounded by electrons in shells."
        ),
        search_query=primary_query,
    )

    assert set(search.queries) == {primary_query, alternate_query}
    assert search.max_active == 2
    assert materializer.candidate_calls.count("helium") == 1
    assert sorted(materializer.candidate_calls) == ["bohr", "helium"]
    assert result.source == "search"


@pytest.mark.asyncio
async def test_primary_subject_anchor_outranks_nucleus_word_match() -> None:
    artwork = ImageCandidate(
        source="artwork",
        source_url="https://example.com/artwork",
        image_url="https://example.com/artwork.jpg",
        title="Nucleus Christchurch NZ",
    )
    helium = ImageCandidate(
        source="helium",
        source_url="https://example.com/helium",
        image_url="https://example.com/helium.svg",
        title="Helium atom QM",
    )
    primary_query = "atom structure nucleus"
    alternate_query = "atom nucleus electron shell"
    search = ParallelSearchProvider(
        {
            primary_query: [artwork, helium],
            alternate_query: [],
        }
    )
    materializer = RecordingMaterializer()
    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=Evaluator(),
        generation_provider=Generator(),
        materializer=materializer,
        review_limit=1,
    )

    result = await resolver.resolve(
        requirement=(
            "A diagram of an atom showing the central nucleus containing protons "
            "and neutrons, surrounded by electrons in shells."
        ),
        search_query=primary_query,
    )

    assert materializer.candidate_calls == ["helium"]
    assert result.candidate is helium


@pytest.mark.asyncio
async def test_failed_materialization_is_bounded_to_eight_candidates() -> None:
    candidates = [
        ImageCandidate(
            source=f"candidate-{index}",
            source_url=f"https://example.com/source/{index}",
            image_url=f"https://example.com/image/{index}.jpg",
            title=f"Plant cell {index}",
        )
        for index in range(20)
    ]
    search = ParallelSearchProvider({"plant cell": candidates})
    materializer = RecordingMaterializer(fail_candidates=True)
    generator = Generator()
    resolver = ImageResolver(
        search_provider=search,
        evaluation_provider=Evaluator(),
        generation_provider=generator,
        materializer=materializer,
    )

    result = await resolver.resolve(
        requirement="A plant cell",
        search_query="plant cell",
    )

    assert len(materializer.candidate_calls) == resolver.MAX_MATERIALIZATION_ATTEMPTS
    assert result.source == "generated"
    assert generator.calls == 1
