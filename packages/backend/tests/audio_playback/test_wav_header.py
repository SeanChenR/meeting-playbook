"""Tests for parse_wav_header — slice-16 task 2.1.

Per design *AudioRangeServer 為 deep module + 純函式 WAV header 解析* (layer 1):
- 標準 44-byte header → data_offset = 44
- header 含 36-byte LIST chunk → data_offset > 44
- 48kHz fixture → raise UnsupportedWavFormat with sample_rate
- stereo fixture → raise UnsupportedWavFormat with channels
"""

from __future__ import annotations

import struct

import pytest

from meeting_playbook.audio_playback.wav_header import (
    InvalidRange,
    UnsupportedWavFormat,
    WavHeaderInfo,
    compute_byte_range,
    parse_wav_header,
)


def _wav_header(
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    bits_per_sample: int = 16,
    extra_chunks: bytes = b"",
    data_bytes_len: int = 32_000,
) -> bytes:
    """Build a minimal RIFF/WAVE header byte string for testing.

    Caller supplies optional `extra_chunks` (raw bytes inserted between
    the fmt chunk and the data chunk) so we can simulate a LIST chunk.
    """
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)  # fmt chunk size (PCM)
        + struct.pack("<H", 1)  # audio_format: PCM
        + struct.pack("<H", channels)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bits_per_sample)
    )
    data_chunk_header = b"data" + struct.pack("<I", data_bytes_len)
    payload = b"WAVE" + fmt_chunk + extra_chunks + data_chunk_header
    riff = b"RIFF" + struct.pack("<I", len(payload) + 4) + payload
    return riff


def test_standard_44_byte_header_data_offset_is_44() -> None:
    """Mono 16-bit 16 kHz with no extra chunks: data starts at byte 44."""
    header = _wav_header()
    info = parse_wav_header(header)
    assert info.data_offset == 44
    assert info.sample_rate == 16000
    assert info.channels == 1
    assert info.bits_per_sample == 16
    assert info.data_bytes == 32_000


def test_list_chunk_pushes_data_offset_beyond_44() -> None:
    """A 36-byte LIST chunk (header + payload) sits between fmt and data."""
    list_chunk = (
        b"LIST"
        + struct.pack("<I", 28)  # payload length
        + b"INFO"
        + b"INAM"
        + struct.pack("<I", 16)
        + b"meeting-playbook"
    )
    header = _wav_header(extra_chunks=list_chunk)
    info = parse_wav_header(header)
    # 44 (standard) + 8 (LIST header) + 28 (LIST payload) = 80
    assert info.data_offset == 80, f"expected 80, got {info.data_offset}"


def test_48khz_raises_unsupported_with_sample_rate_in_message() -> None:
    header = _wav_header(sample_rate=48000)
    with pytest.raises(UnsupportedWavFormat) as exc_info:
        parse_wav_header(header)
    assert "sample_rate" in str(exc_info.value).lower() or "48000" in str(exc_info.value)


def test_stereo_raises_unsupported_with_channels_in_message() -> None:
    header = _wav_header(channels=2)
    with pytest.raises(UnsupportedWavFormat) as exc_info:
        parse_wav_header(header)
    assert "channels" in str(exc_info.value).lower() or "2" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Task 2.2 — compute_byte_range
# ---------------------------------------------------------------------------


def _hdr_40s() -> WavHeaderInfo:
    """Header info for a 40-second 16 kHz mono 16-bit PCM file (1.28 MB data)."""
    return WavHeaderInfo(
        data_offset=44,
        sample_rate=16000,
        channels=1,
        bits_per_sample=16,
        data_bytes=40 * 16000 * 2,  # 40 seconds * 32000 bytes/sec
    )


def test_compute_byte_range_5s_to_15s_on_40s_wav() -> None:
    """A 10-second slice from 5s to 15s on a 40s WAV yields (160_044, 480_043)."""
    header = _hdr_40s()
    start, end = compute_byte_range(header=header, start_second=5, end_second=15)
    assert (start, end) == (160_044, 480_043), f"got ({start}, {end})"


def test_compute_byte_range_rejects_reversed_interval() -> None:
    header = _hdr_40s()
    with pytest.raises(InvalidRange):
        compute_byte_range(header=header, start_second=15, end_second=5)


def test_compute_byte_range_rejects_out_of_bounds() -> None:
    """Both bounds past the end of the data chunk."""
    header = _hdr_40s()
    with pytest.raises(InvalidRange):
        compute_byte_range(header=header, start_second=100, end_second=110)


def test_compute_byte_range_boundary_cases() -> None:
    """Spec example block: three boundary cases all clamp / align correctly."""
    header = _hdr_40s()
    # (a) start at 0 → returns data_offset; end at full duration → returns last byte.
    start, end = compute_byte_range(header=header, start_second=0, end_second=40)
    assert start == 44
    assert end == 44 + (40 * 16000 * 2) - 1  # 1_280_043

    # (b) tiny but positive slice (0.5s) → block-aligned, inside data.
    start, end = compute_byte_range(header=header, start_second=10, end_second=10.5)
    assert start == 44 + (10 * 16000 * 2)
    assert end == 44 + int(10.5 * 16000 * 2) - 1
    assert (end - start + 1) % 2 == 0  # block-aligned

    # (c) end past file: should still clamp to file end without raising
    # (we *raise* only when BOTH bounds are outside; start inside + end past
    # is treated as "give me what you have").
    start, end = compute_byte_range(header=header, start_second=39, end_second=50)
    assert end == 44 + (40 * 16000 * 2) - 1  # clamped to last byte
