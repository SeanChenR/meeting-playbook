"""HTTP Range parsing + AudioRangeServer deep module — slice-16 task 3.1.

Layered design (per design.md decision *AudioRangeServer 為 deep module*):
- `parse_range_header(value, total_length) -> (start, end)` is a pure
  function the deep module composes with `parse_wav_header` and
  `compute_byte_range` to serve a single Range request.
- `AudioRangeServer.serve(...)` is the deep entry point: caller hands
  it a file path + chunk metadata + optional Range header and gets back
  a `RangeResponse` ready to translate into a FastAPI Response.

The serve layer reads only the first 4 KiB of the file to parse the WAV
header. The body is yielded as a generator so FastAPI's StreamingResponse
can pipe it out without buffering the whole 30-minute WAV in memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from meeting_playbook.audio_playback.wav_header import parse_wav_header


class MalformedRange(Exception):
    """Raised when an HTTP Range header is syntactically invalid."""


class RangeNotSatisfiable(Exception):
    """Raised when the requested byte range is outside the file's bounds."""


_HEADER_READ_BYTES = 4096
_STREAM_CHUNK_BYTES = 64 * 1024


_RANGE_RE = re.compile(r"^bytes=(?P<spec>.+)$")


def parse_range_header(value: str, total_length: int) -> tuple[int, int]:
    """Parse an HTTP `Range` header value into an inclusive (start, end).

    Supports the three RFC 7233 single-range forms:
        bytes=A-B       absolute span
        bytes=A-        from A to end of resource
        bytes=-N        last N bytes
    Multi-range syntax (`bytes=0-100,200-300`) is rejected — the audio
    pipeline never needs it and supporting it would force the deep module
    to emit multipart bodies.
    """
    if not value:
        raise MalformedRange("empty Range header")
    m = _RANGE_RE.match(value)
    if not m:
        raise MalformedRange(f"Range must begin with 'bytes='; got {value!r}")
    spec = m.group("spec")
    if "," in spec:
        raise MalformedRange("multi-range syntax not supported")
    parts = spec.split("-", maxsplit=1)
    if len(parts) != 2:
        raise MalformedRange(f"Range spec must contain '-'; got {spec!r}")
    start_s, end_s = parts[0], parts[1]

    if start_s == "" and end_s == "":
        raise MalformedRange("Range spec must have a start or end")
    if start_s == "":
        # suffix form: last N bytes
        try:
            suffix_len = int(end_s)
        except ValueError as e:
            raise MalformedRange(f"suffix length must be int; got {end_s!r}") from e
        if suffix_len <= 0:
            raise MalformedRange(f"suffix length must be > 0; got {suffix_len}")
        start = max(0, total_length - suffix_len)
        end = total_length - 1
        return start, end

    try:
        start = int(start_s)
    except ValueError as e:
        raise MalformedRange(f"start must be int; got {start_s!r}") from e
    if start < 0:
        raise MalformedRange(f"start must be >= 0; got {start}")
    if start >= total_length:
        raise MalformedRange(f"start ({start}) >= total_length ({total_length})")

    if end_s == "":
        end = total_length - 1
    else:
        try:
            end = int(end_s)
        except ValueError as e:
            raise MalformedRange(f"end must be int; got {end_s!r}") from e
        if end < start:
            raise MalformedRange(f"end ({end}) < start ({start})")
        end = min(end, total_length - 1)

    return start, end


@dataclass(frozen=True)
class RangeResponse:
    """Output of `AudioRangeServer.serve`. Caller wires it to an HTTP framework.

    `body` is a generator of bytes chunks so the response can stream
    without loading the whole slice into memory.
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Iterable[bytes] = field(default_factory=tuple)


class AudioRangeServer:
    """Deep module: file + chunk metadata + Range header → RangeResponse."""

    @staticmethod
    def serve(
        *,
        file_path: Path,
        recording_started_at: datetime,
        chunk_start: datetime,
        chunk_end: datetime,
        range_header: str | None,
        max_bytes: int,
    ) -> RangeResponse:
        """Stream a Range slice (or the full WAV file) of a 16 kHz mono PCM file.

        The HTML5 `<audio>` element decodes WAV by reading the file
        header first, then issues follow-up Range requests for seeking.
        So the contract is:
        - No Range → 200 + entire file (header + all PCM bytes).
        - With Range → 206 + the requested byte range.
        - In both cases the body is capped at `max_bytes` so a single
          request can't exhaust the budget; the browser issues a
          follow-up Range for the rest.

        `recording_started_at` / `chunk_start` / `chunk_end` are accepted
        for future per-chunk synthesis strategies (returning a freshly
        crafted micro-WAV per chunk) but are currently unused — the
        canonical contract is "stream the WAV file, honor Range". We
        still parse the WAV header eagerly so an unsupported file format
        surfaces as 500 instead of an opaque mid-body streaming error.
        """
        total_length = file_path.stat().st_size

        with file_path.open("rb") as fh:
            header_bytes = fh.read(_HEADER_READ_BYTES)
        parse_wav_header(header_bytes)  # validates the file is decodable
        _unused = (recording_started_at, chunk_start, chunk_end)

        if range_header is None:
            requested_start = 0
            requested_end = total_length - 1
            status_code = 200
        else:
            requested_start, requested_end = parse_range_header(range_header, total_length)
            status_code = 206

        body_byte_count = requested_end - requested_start + 1
        if body_byte_count > max_bytes:
            requested_end = requested_start + max_bytes - 1

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": "audio/wav",
            "Content-Length": str(requested_end - requested_start + 1),
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {requested_start}-{requested_end}/{total_length}"

        body = _stream_file_range(file_path, requested_start, requested_end)
        return RangeResponse(status_code=status_code, headers=headers, body=body)


def _stream_file_range(path: Path, start: int, end_inclusive: int) -> Iterator[bytes]:
    """Yield the slice [start, end_inclusive] of `path` in fixed-size chunks."""
    remaining = end_inclusive - start + 1
    if remaining <= 0:
        return
    with path.open("rb") as fh:
        fh.seek(start)
        while remaining > 0:
            chunk_size = min(_STREAM_CHUNK_BYTES, remaining)
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)
