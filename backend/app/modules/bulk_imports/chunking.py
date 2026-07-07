# ========================== #
#   bulk_imports_chunking.py #
# ========================== #

"""Chunking helpers for tenant bulk import processing."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Generic, Iterable, TypeVar


RowItem = TypeVar("RowItem")


DEFAULT_IMPORT_CHUNK_SIZE = 100


class ImportChunkingError(ValueError):
    """Raised when import chunking receives invalid input."""


@dataclass(frozen=True)
class ImportChunk(Generic[RowItem]):
    """A group of import rows processed together."""

    chunk_number: int
    start_index: int
    end_index: int
    items: list[RowItem]

    @property
    def size(self) -> int:
        """Return the number of items in this chunk."""

        return len(self.items)


def validate_chunk_size(chunk_size: int) -> None:
    """Validate the requested chunk size."""

    if chunk_size <= 0:
        raise ImportChunkingError("chunk_size must be greater than zero.")


def calculate_total_chunks(
    *,
    total_items: int,
    chunk_size: int = DEFAULT_IMPORT_CHUNK_SIZE,
) -> int:
    """Calculate how many chunks are needed for a number of items."""

    validate_chunk_size(chunk_size)

    if total_items <= 0:
        return 0

    return ceil(total_items / chunk_size)


def build_import_chunk(
    *,
    chunk_number: int,
    start_index: int,
    end_index: int,
    items: list[RowItem],
) -> ImportChunk[RowItem]:
    """Build one import chunk object."""

    return ImportChunk(
        chunk_number=chunk_number,
        start_index=start_index,
        end_index=end_index,
        items=items,
    )


def chunk_import_items(
    *,
    items: list[RowItem],
    chunk_size: int = DEFAULT_IMPORT_CHUNK_SIZE,
) -> list[ImportChunk[RowItem]]:
    """Split import items into fixed-size chunks."""

    validate_chunk_size(chunk_size)

    chunks: list[ImportChunk[RowItem]] = []

    for start_index in range(0, len(items), chunk_size):
        end_index = min(start_index + chunk_size, len(items))
        chunk_items = items[start_index:end_index]
        chunk_number = len(chunks) + 1

        chunk = build_import_chunk(
            chunk_number=chunk_number,
            start_index=start_index,
            end_index=end_index,
            items=chunk_items,
        )
        chunks.append(chunk)

    return chunks


def iter_import_chunks(
    *,
    items: Iterable[RowItem],
    chunk_size: int = DEFAULT_IMPORT_CHUNK_SIZE,
) -> Iterable[ImportChunk[RowItem]]:
    """Yield chunks from any iterable without requiring the caller to build chunks manually."""

    validate_chunk_size(chunk_size)

    current_items: list[RowItem] = []
    start_index = 0
    chunk_number = 1

    for item_index, item in enumerate(items):
        current_items.append(item)

        if len(current_items) == chunk_size:
            end_index = item_index + 1

            yield build_import_chunk(
                chunk_number=chunk_number,
                start_index=start_index,
                end_index=end_index,
                items=current_items,
            )

            chunk_number += 1
            start_index = end_index
            current_items = []

    if current_items:
        yield build_import_chunk(
            chunk_number=chunk_number,
            start_index=start_index,
            end_index=start_index + len(current_items),
            items=current_items,
        )