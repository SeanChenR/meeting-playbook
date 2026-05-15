"""Post-transcode duration enforcement tests — slice-14 task 3.2.

Verifies the spec scenario `Duration over budget rejects without recording row`:
- WAV under the budget → no exception, file remains on disk
- WAV over the budget → `OfflineIngestTooLong` raised AND the WAV is unlinked

Uses a 1-second WAV with `max_seconds=30` for the under-budget case and a
60-second WAV with `max_seconds=10` for the over-budget case. Same code
path as production (which compares against 10800 / 3 hours), just with
test-scale constants so we avoid writing a multi-MB fixture.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from meeting_playbook.offline_ingest.pipeline import (
    OfflineIngestTooLong,
    enforce_max_duration,
)


def _write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 16_000) -> None:
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{frame_count}h", *([0] * frame_count)))


def test_enforce_max_duration_under_budget_keeps_file(tmp_path: Path) -> None:
    wav = tmp_path / "short.wav"
    _write_silent_wav(wav, duration_seconds=1.0)

    enforce_max_duration(wav, max_seconds=30)

    assert wav.exists(), "under-budget WAV MUST remain on disk"


def test_enforce_max_duration_over_budget_raises_and_unlinks(tmp_path: Path) -> None:
    wav = tmp_path / "long.wav"
    _write_silent_wav(wav, duration_seconds=60.0)

    with pytest.raises(OfflineIngestTooLong) as excinfo:
        enforce_max_duration(wav, max_seconds=10)

    assert not wav.exists(), "over-budget WAV MUST be unlinked"
    # The exception should carry the actual duration so logs / progress
    # endpoint can surface it to operators.
    assert excinfo.value.duration_seconds >= 60.0
    assert excinfo.value.max_seconds == 10
