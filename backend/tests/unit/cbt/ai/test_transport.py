from __future__ import annotations

import gzip
import zlib

import pytest

from app.modules.cbt.ai.transport import CBTGZipRoute


def test_safe_gunzip_round_trip() -> None:
    raw = b'{"data_base64":"AAAA"}' * 2_000
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

    with pytest.raises((ValueError, zlib.error)):
        CBTGZipRoute._safe_gunzip(
            compressed[:-3],
            max_output_bytes=1_024,
        )


def test_safe_gunzip_rejects_concatenated_members() -> None:
    payload = gzip.compress(b"first") + gzip.compress(b"second")

    with pytest.raises(ValueError, match="concatenated"):
        CBTGZipRoute._safe_gunzip(payload, max_output_bytes=1_024)


def test_accept_encoding_respects_gzip_quality_zero() -> None:
    assert CBTGZipRoute._accepts_gzip(b"br, gzip") is True
    assert CBTGZipRoute._accepts_gzip(b"gzip;q=1.0") is True
    assert CBTGZipRoute._accepts_gzip(b"gzip;q=0") is False
