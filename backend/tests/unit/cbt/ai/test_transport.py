from __future__ import annotations

import gzip

import pytest

from app.modules.cbt.ai.transport import CBTGZipRoute


def test_safe_gunzip_round_trip() -> None:
    raw = (b'{"data_base64":"AAAA"}' * 2_000)
    compressed = gzip.compress(raw)

    restored = CBTGZipRoute._safe_gunzip(
        compressed,
        max_output_bytes=len(raw) + 10,
    )

    assert restored == raw


def test_safe_gunzip_rejects_output_over_limit() -> None:
    raw = b"A" * 100_000
    compressed = gzip.compress(raw)

    with pytest.raises(OverflowError):
        CBTGZipRoute._safe_gunzip(compressed, max_output_bytes=1_024)


def test_safe_gunzip_rejects_incomplete_stream() -> None:
    compressed = gzip.compress(b"payload")

    with pytest.raises((ValueError, Exception)):
        CBTGZipRoute._safe_gunzip(
            compressed[:-3],
            max_output_bytes=1_024,
        )
