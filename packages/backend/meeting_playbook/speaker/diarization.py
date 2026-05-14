"""DiarizationProvider Protocol + DiarizationSegment dataclass.

Mirrors the `ASRProvider` Protocol (ADR-0005) — concrete providers
(`PyannoteProvider`, `AppleSpeechProvider`, future cloud impls) implement
this contract; the speaker attribution layer depends ONLY on this Protocol
so a new diarization engine is a drop-in via dependency injection.

See spec `speaker-attribution-strategy/spec.md` for the normative contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DiarizationSegment:
    """One contiguous span of audio attributed to a single speaker cluster.

    `cluster_id` is 1-based. Two segments with the same `cluster_id` came
    from the same diarization-time speaker hypothesis; matching cluster ids
    across providers is meaningless.
    """

    start_ms: int
    end_ms: int
    cluster_id: int


class DiarizationProviderUnavailable(RuntimeError):
    """Raised when a `DiarizationProvider` cannot run on the current host
    (missing credential, wrong platform, missing optional dependency).

    Callers can catch this to fall back to a different provider.
    """


@runtime_checkable
class DiarizationProvider(Protocol):
    """Behavioural contract for diarization engines.

    Implementations MUST:
    - Accept a 16kHz mono WAV `Path`; behaviour on other formats is unspecified.
    - Return a list of `DiarizationSegment` sorted by `start_ms` ascending.
    - Guarantee no temporal overlap between consecutive segments
      (`segments[i].end_ms <= segments[i+1].start_ms`).
    - Use 1-based `cluster_id` values.
    - Raise `DiarizationProviderUnavailable` on host / config issues — never
      silently return empty results to mask unavailability.
    """

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]: ...
