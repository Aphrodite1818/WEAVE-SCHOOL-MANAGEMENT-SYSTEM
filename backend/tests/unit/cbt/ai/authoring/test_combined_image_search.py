from __future__ import annotations

import asyncio

import pytest

from app.modules.cbt.ai.authoring.providers.base import ImageCandidate
from app.modules.cbt.ai.authoring.providers.combined_search import CombinedImageSearchProvider
from app.modules.cbt.ai.authoring.providers.wikimedia import WikimediaCommonsImageSearchProvider


class _ConcurrencyTracker:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0


class _FakeSearchProvider:
    def __init__(self, name: str, results, tracker: _ConcurrencyTracker, *, error=None) -> None:
        self.provider_name = name
        self.results = list(results)
        self.tracker = tracker
        self.error = error
        self.calls: list[str] = []

    def is_configured(self) -> bool:
        return True

    async def search(self, *, query, limit=10, metadata=None):
        self.calls.append(query)
        self.tracker.active += 1
        self.tracker.max_active = max(self.tracker.max_active, self.tracker.active)
        try:
            await asyncio.sleep(0.01)
            if self.error is not None:
                raise self.error
            return self.results[:limit]
        finally:
            self.tracker.active -= 1


def _candidate(source: str, title: str, source_url: str, image_url: str) -> ImageCandidate:
    return ImageCandidate(
        source=source,
        source_url=source_url,
        image_url=image_url,
        title=title,
    )


@pytest.mark.asyncio
async def test_combined_search_runs_sources_concurrently_and_interleaves_results() -> None:
    tracker = _ConcurrencyTracker()
    commons = _FakeSearchProvider(
        "wikimedia_commons",
        [
            _candidate(
                "wikimedia_commons",
                "Animal cell",
                "https://commons.wikimedia.org/wiki/File:Animal_cell.svg",
                "https://upload.wikimedia.org/animal-cell.png",
            ),
            _candidate(
                "wikimedia_commons",
                "Plant cell",
                "https://commons.wikimedia.org/wiki/File:Plant_cell.svg",
                "https://upload.wikimedia.org/plant-cell.png",
            ),
        ],
        tracker,
    )
    openverse = _FakeSearchProvider(
        "openverse",
        [
            _candidate(
                "wellcome_collection",
                "Human anatomy",
                "https://wellcomecollection.org/works/anatomy",
                "https://iiif.wellcomecollection.org/anatomy.jpg",
            ),
            _candidate(
                "nasa",
                "Solar system",
                "https://images.nasa.gov/details/solar-system",
                "https://images-assets.nasa.gov/solar-system.jpg",
            ),
        ],
        tracker,
    )
    provider = CombinedImageSearchProvider((commons, openverse))

    results = await provider.search(query="cell anatomy", limit=4)

    assert tracker.max_active == 2
    assert [candidate.source for candidate in results] == [
        "wikimedia_commons",
        "wellcome_collection",
        "wikimedia_commons",
        "nasa",
    ]


@pytest.mark.asyncio
async def test_combined_search_dedupes_same_underlying_commons_file_across_sources() -> None:
    tracker = _ConcurrencyTracker()
    commons_source_url = "https://commons.wikimedia.org/wiki/File:Animal_cell.svg"
    commons = _FakeSearchProvider(
        "wikimedia_commons",
        [
            _candidate(
                "wikimedia_commons",
                "Animal cell",
                commons_source_url,
                "https://upload.wikimedia.org/thumb/animal-cell.png",
            )
        ],
        tracker,
    )
    openverse = _FakeSearchProvider(
        "openverse",
        [
            _candidate(
                "wikimedia",
                "Animal cell",
                commons_source_url,
                "https://upload.wikimedia.org/original/animal-cell.svg",
            ),
            _candidate(
                "wellcome_collection",
                "Cell microscopy",
                "https://wellcomecollection.org/works/cell",
                "https://iiif.wellcomecollection.org/cell.jpg",
            ),
        ],
        tracker,
    )
    provider = CombinedImageSearchProvider((commons, openverse))

    results = await provider.search(query="animal cell", limit=3)

    assert len(results) == 2
    assert results[0].source == "wikimedia_commons"
    assert results[1].source == "wellcome_collection"


@pytest.mark.asyncio
async def test_combined_search_keeps_working_when_one_source_fails() -> None:
    tracker = _ConcurrencyTracker()
    commons_result = _candidate(
        "wikimedia_commons",
        "Atom diagram",
        "https://commons.wikimedia.org/wiki/File:Atom_diagram.svg",
        "https://upload.wikimedia.org/thumb/atom.png",
    )
    commons = _FakeSearchProvider("wikimedia_commons", [commons_result], tracker)
    openverse = _FakeSearchProvider(
        "openverse",
        [],
        tracker,
        error=RuntimeError("Openverse unavailable"),
    )
    provider = CombinedImageSearchProvider((commons, openverse))

    results = await provider.search(query="atom diagram", limit=5)

    assert results == [commons_result]


def test_wikimedia_normalization_prefers_raster_thumbnail_and_keeps_license() -> None:
    provider = WikimediaCommonsImageSearchProvider()
    page = {
        "pageid": 123,
        "title": "File:Animal cell.svg",
        "fullurl": "https://commons.wikimedia.org/wiki/File:Animal_cell.svg",
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Animal_cell.svg",
                "thumburl": (
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
                    "Animal_cell.svg/1600px-Animal_cell.svg.png"
                ),
                "width": 2000,
                "height": 1800,
                "thumbwidth": 1600,
                "thumbheight": 1440,
                "mime": "image/svg+xml",
                "extmetadata": {
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                    "Artist": {"value": "<b>Example Author</b>"},
                },
            }
        ],
    }

    candidate = provider._normalize_candidate(page, metadata={})

    assert candidate is not None
    assert candidate.source == "wikimedia_commons"
    assert candidate.title == "Animal cell.svg"
    assert candidate.image_url.endswith("1600px-Animal_cell.svg.png")
    assert candidate.mime_type == "image/png"
    assert candidate.license_name == "CC BY-SA 4.0"
    assert candidate.creator == "Example Author"


def test_wikimedia_rejects_noncommercial_license_metadata() -> None:
    provider = WikimediaCommonsImageSearchProvider()
    page = {
        "pageid": 456,
        "title": "File:Restricted image.jpg",
        "fullurl": "https://commons.wikimedia.org/wiki/File:Restricted_image.jpg",
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/restricted.jpg",
                "width": 1000,
                "height": 800,
                "mime": "image/jpeg",
                "extmetadata": {
                    "LicenseShortName": {"value": "CC BY-NC 4.0"},
                },
            }
        ],
    }

    assert provider._normalize_candidate(page, metadata={}) is None
