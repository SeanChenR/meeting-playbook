"""Transcode subprocess tests — slice-14 task 3.1.

Verifies the spec scenarios under
"ffmpeg subprocess normalises to 16kHz mono WAV":
- Successful transcode writes the canonical WAV path
- ffmpeg failure surfaces transcode error

Uses a tiny in-test WAV as input. Because the source is already 16kHz mono
PCM, ffmpeg round-trips it; the test still exercises the full subprocess
spawn + return-code handling + staging cleanup.

Skipped when `ffmpeg` is not on PATH (we don't ship the binary; the
production environment is expected to have it per README §3 setup).
"""

from __future__ import annotations

import asyncio
import shutil
import struct
import wave
from pathlib import Path

import pytest

from meeting_playbook.offline_ingest.transcode import (
    OfflineIngestTranscodeError,
    transcode_to_canonical_wav,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not on PATH; transcode tests skipped",
)


def _write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 16_000) -> None:
    """Write a tiny 16kHz mono PCM silent WAV at `path`."""
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{frame_count}h", *([0] * frame_count)))


def test_transcode_writes_canonical_wav_and_unlinks_staging(tmp_path: Path) -> None:
    staging = tmp_path / "upload_abc.partial"
    output = tmp_path / "meeting_xyz" / "source.wav"
    _write_silent_wav(staging, duration_seconds=1.0)

    asyncio.run(transcode_to_canonical_wav(staging_path=staging, output_path=output))

    assert output.exists(), "transcoded WAV must exist at the output path"
    assert not staging.exists(), "staging .partial file must be unlinked on success"

    with wave.open(str(output), "rb") as wf:
        assert wf.getnchannels() == 1, "output must be mono"
        assert wf.getframerate() == 16_000, "output must be 16kHz"
        assert wf.getsampwidth() == 2, "output must be 16-bit"


def test_transcode_raises_when_ffmpeg_fails_on_corrupt_input(tmp_path: Path) -> None:
    """A staging file that is not a valid audio container makes ffmpeg
    return non-zero. The transcoder MUST raise `OfflineIngestTranscodeError`
    and unlink the staging file (per spec scenario "ffmpeg failure
    surfaces transcode error").
    """
    staging = tmp_path / "corrupt.partial"
    staging.write_bytes(b"this is definitely not audio data")
    output = tmp_path / "meeting_xyz" / "source.wav"

    with pytest.raises(OfflineIngestTranscodeError) as excinfo:
        asyncio.run(transcode_to_canonical_wav(staging_path=staging, output_path=output))

    assert not staging.exists(), (
        "staging file MUST be removed even when ffmpeg fails, to avoid disk leaks"
    )
    assert not output.exists(), "partial output MUST not survive a failed transcode"
    # The error message should carry some ffmpeg stderr hint so operators
    # can diagnose the failure without needing to re-run.
    assert str(excinfo.value), "error message must be non-empty"
