"""Tests for parse_range_header + AudioRangeServer.serve — slice-16 task 3.1.

Parser (pure): bytes=A-B / bytes=A- / bytes=-N / malformed.
Serve (deep): full file (no Range), partial Range slice, max_bytes cap.
"""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

import pytest

from meeting_playbook.audio_playback.range_server import (
    AudioRangeServer,
    MalformedRange,
    parse_range_header,
)

# ---------------------------------------------------------------------------
# parse_range_header
# ---------------------------------------------------------------------------


def test_parse_range_bytes_a_b() -> None:
    assert parse_range_header("bytes=100-200", total_length=1000) == (100, 200)


def test_parse_range_bytes_a_open() -> None:
    """`bytes=500-` on a 1000-byte resource → clamp END to 999 inclusive."""
    assert parse_range_header("bytes=500-", total_length=1000) == (500, 999)


def test_parse_range_suffix_form() -> None:
    """`bytes=-200` on 1000 bytes → last 200 bytes (offsets 800-999)."""
    assert parse_range_header("bytes=-200", total_length=1000) == (800, 999)


def test_parse_range_invalid_unit_raises() -> None:
    with pytest.raises(MalformedRange):
        parse_range_header("items=0-10", total_length=1000)


def test_parse_range_start_greater_than_end_raises() -> None:
    with pytest.raises(MalformedRange):
        parse_range_header("bytes=200-100", total_length=1000)


def test_parse_range_start_past_total_raises() -> None:
    with pytest.raises(MalformedRange):
        parse_range_header("bytes=2000-3000", total_length=1000)


# ---------------------------------------------------------------------------
# AudioRangeServer.serve
# ---------------------------------------------------------------------------


def _write_40s_wav(path: Path) -> int:
    """Write a 40-second 16 kHz mono 16-bit PCM WAV. Returns total byte size."""
    sample_rate = 16000
    channels = 1
    bits_per_sample = 16
    duration_s = 40
    data_bytes_len = sample_rate * channels * (bits_per_sample // 8) * duration_s
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", channels)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bits_per_sample)
    )
    data_header = b"data" + struct.pack("<I", data_bytes_len)
    # Payload is just deterministic zero-byte samples — content doesn't
    # matter for byte-range assertions.
    data_payload = b"\x00" * data_bytes_len
    payload = b"WAVE" + fmt_chunk + data_header + data_payload
    riff = b"RIFF" + struct.pack("<I", len(payload) + 4) + payload
    path.write_bytes(riff)
    return len(riff)


def _drain(body) -> bytes:
    """Collect the AsyncIterator-ish body into a single bytes payload (sync helper)."""
    chunks: list[bytes] = []
    for chunk in body:
        chunks.append(chunk)
    return b"".join(chunks)


def test_serve_with_range_returns_206_and_byte_aligned_slice(tmp_path: Path) -> None:
    """A Range request for a 10-second slice from 5s to 15s returns 206 +
    the WAV bytes at offsets 160044-480043 inclusive.
    """
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)

    started_at = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    chunk_start = datetime(2026, 5, 15, 10, 0, 5, tzinfo=UTC)
    chunk_end = datetime(2026, 5, 15, 10, 0, 15, tzinfo=UTC)

    resp = AudioRangeServer.serve(
        file_path=wav,
        recording_started_at=started_at,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        range_header="bytes=160044-480043",
        max_bytes=10 * 1024 * 1024,
    )
    assert resp.status_code == 206
    assert resp.headers["Content-Range"] == f"bytes 160044-480043/{total}"
    body = _drain(resp.body)
    assert len(body) == 480043 - 160044 + 1


def test_serve_without_range_returns_200_full_body(tmp_path: Path) -> None:
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)

    started_at = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    chunk_start = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    chunk_end = datetime(2026, 5, 15, 10, 0, 40, tzinfo=UTC)

    resp = AudioRangeServer.serve(
        file_path=wav,
        recording_started_at=started_at,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        range_header=None,
        max_bytes=10 * 1024 * 1024,
    )
    assert resp.status_code == 200
    body = _drain(resp.body)
    assert len(body) == total


def test_serve_caps_body_at_max_bytes(tmp_path: Path) -> None:
    """When the requested range exceeds max_bytes, the body is truncated."""
    wav = tmp_path / "session.wav"
    _write_40s_wav(wav)

    started_at = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    chunk_start = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    chunk_end = datetime(2026, 5, 15, 10, 0, 40, tzinfo=UTC)

    max_bytes = 256 * 1024  # 256 KiB
    resp = AudioRangeServer.serve(
        file_path=wav,
        recording_started_at=started_at,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        range_header=None,
        max_bytes=max_bytes,
    )
    body = _drain(resp.body)
    assert len(body) <= max_bytes
