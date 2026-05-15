"""Pure WAV header parsing — slice-16 task 2.1 + 2.2.

The functions here are the inner layer of the `AudioRangeServer` deep
module: they don't touch the filesystem. The caller passes raw header
bytes (typically the first ~4 KiB of the WAV file) plus an `(start, end)`
second interval; we return where on disk the corresponding PCM bytes
live so the serve layer can stream them out.

The project's audio capture pipeline always writes 16 kHz mono 16-bit PCM
WAV files (see ADR-0028 + sessions/router.py). Anything else is a
configuration error; `parse_wav_header` rejects it explicitly so the
calling endpoint can return 500 with a precise message rather than
slicing the wrong byte range.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


class UnsupportedWavFormat(Exception):
    """Raised when the WAV header does not match the project's PCM contract.

    Carries a structured `reason` so the caller (HTTP endpoint, test) can
    surface a precise error code without re-parsing the message.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidRange(Exception):
    """Raised when the requested second interval cannot map to bytes."""


@dataclass(frozen=True)
class WavHeaderInfo:
    """Parsed metadata for a 16 kHz mono 16-bit PCM WAV file."""

    data_offset: int
    """Byte offset where the PCM `data` chunk's payload starts."""

    sample_rate: int
    channels: int
    bits_per_sample: int
    data_bytes: int
    """Length of the PCM payload in bytes (i.e., the `data` chunk size)."""


_REQUIRED_SAMPLE_RATE = 16000
_REQUIRED_CHANNELS = 1
_REQUIRED_BITS_PER_SAMPLE = 16


def parse_wav_header(header_bytes: bytes) -> WavHeaderInfo:
    """Parse a RIFF/WAVE header and return the format metadata.

    Tolerates non-`fmt `/`data` chunks (LIST/JUNK/etc.) by skipping them.
    Rejects non-16 kHz mono 16-bit PCM with `UnsupportedWavFormat`.
    """
    if len(header_bytes) < 12 or header_bytes[:4] != b"RIFF" or header_bytes[8:12] != b"WAVE":
        raise UnsupportedWavFormat("missing RIFF/WAVE container")

    offset = 12  # skip RIFF + size + WAVE
    fmt_seen = False
    sample_rate = 0
    channels = 0
    bits_per_sample = 0
    audio_format = 0

    while offset + 8 <= len(header_bytes):
        chunk_id = header_bytes[offset : offset + 4]
        (chunk_size,) = struct.unpack_from("<I", header_bytes, offset + 4)
        chunk_payload_start = offset + 8

        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise UnsupportedWavFormat(f"fmt chunk too small: {chunk_size}")
            (
                audio_format,
                channels,
                sample_rate,
                _byte_rate,
                _block_align,
                bits_per_sample,
            ) = struct.unpack_from("<HHIIHH", header_bytes, chunk_payload_start)
            fmt_seen = True
        elif chunk_id == b"data":
            if not fmt_seen:
                raise UnsupportedWavFormat("data chunk appears before fmt chunk")
            if audio_format != 1:
                raise UnsupportedWavFormat(f"audio_format must be 1 (PCM); got {audio_format}")
            if sample_rate != _REQUIRED_SAMPLE_RATE:
                raise UnsupportedWavFormat(
                    f"sample_rate must be {_REQUIRED_SAMPLE_RATE}; got {sample_rate}"
                )
            if channels != _REQUIRED_CHANNELS:
                raise UnsupportedWavFormat(f"channels must be {_REQUIRED_CHANNELS}; got {channels}")
            if bits_per_sample != _REQUIRED_BITS_PER_SAMPLE:
                raise UnsupportedWavFormat(
                    f"bits_per_sample must be {_REQUIRED_BITS_PER_SAMPLE}; got {bits_per_sample}"
                )
            return WavHeaderInfo(
                data_offset=chunk_payload_start,
                sample_rate=sample_rate,
                channels=channels,
                bits_per_sample=bits_per_sample,
                data_bytes=chunk_size,
            )

        # Chunk sizes are padded to even bytes per the RIFF spec.
        offset = chunk_payload_start + chunk_size + (chunk_size & 1)

    raise UnsupportedWavFormat("data chunk not found in header window")


def compute_byte_range(
    *,
    header: WavHeaderInfo,
    start_second: float,
    end_second: float,
) -> tuple[int, int]:
    """Translate a second-aligned interval into inclusive byte offsets.

    The returned `(start_byte, end_byte)` are absolute offsets into the
    WAV file (i.e., they already include `header.data_offset`). End is
    inclusive — suitable for `Content-Range: bytes A-B/total` headers.

    Behavior:
    - Block-aligns to the WAV's `block_align` so the returned bytes start
      and end on whole 16-bit samples.
    - Clamps to `[data_offset, data_offset + data_bytes - 1]`.
    - Raises `InvalidRange` when end < start, or when the request lies
      entirely outside the PCM data range.
    """
    if end_second < start_second:
        raise InvalidRange(f"end_second ({end_second}) must be >= start_second ({start_second})")

    bytes_per_second = header.sample_rate * header.channels * (header.bits_per_sample // 8)
    block_align = header.channels * (header.bits_per_sample // 8)
    data_start = header.data_offset
    data_end_inclusive = data_start + header.data_bytes - 1

    raw_start = data_start + int(start_second * bytes_per_second)
    raw_end = data_start + int(end_second * bytes_per_second) - 1

    # Align to block boundaries — floor for start, floor for end+1.
    start_byte = raw_start - ((raw_start - data_start) % block_align)
    end_byte_exclusive = (raw_end + 1) - ((raw_end + 1 - data_start) % block_align)
    end_byte = end_byte_exclusive - 1

    # Clamp inside the data chunk.
    if start_byte > data_end_inclusive or end_byte < data_start:
        raise InvalidRange(
            f"interval [{start_second}, {end_second}] lies outside WAV data "
            f"({header.data_bytes} bytes / {header.data_bytes / bytes_per_second:.2f}s)"
        )
    start_byte = max(start_byte, data_start)
    end_byte = min(end_byte, data_end_inclusive)

    if end_byte < start_byte:
        raise InvalidRange(
            f"computed end_byte ({end_byte}) < start_byte ({start_byte}) after clamping"
        )

    return start_byte, end_byte
