"""FastAPI dependencies for the sessions router.

Slice-11 dropped the per-stream `_whisper_singleton_*` lru_cache + the
`get_asr_providers_dependency` Depends; ASR provider selection is now done
inside the WebSocket handler via `meeting_playbook.asr.factory.
get_asr_providers_for_meeting(meeting.asr_provider)` so it can branch on
the per-meeting engine choice (FastAPI dependencies resolve before the path
parameter is loaded, which is too early to know which engine to build).

Slice-27 (single-channel-recording-entry) — the factory now accepts a
`mode: RecordingMode` argument so the router can route pre-flight:
- `mode == "dual"`   → unchanged. BlackHole required; raises
                       `NoBlackholeDevice` if absent.
- `mode == "single"` → mic-only. The BlackHole discovery routine is NOT
                       invoked (so it cannot raise even if the env override
                       points at a ghost device). Returns a one-entry dict.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from meeting_playbook.audio.capture import AudioCaptureService
from meeting_playbook.audio.devices import (
    NoBlackholeDevice,
    find_blackhole_device,
    find_mic_device,
)
from meeting_playbook.config import get_settings

Stream = Literal["me", "counterparty"]
RecordingMode = Literal["dual", "single"]


# Slice-7: factory returns BOTH stream captures by default (dual mode);
# raises NoBlackholeDevice on missing BlackHole — router maps to error code.
# Slice-27: signature extended with `mode` so single-channel sessions can
# skip the BlackHole pre-flight check.
CaptureFactory = Callable[[str, RecordingMode], dict[Stream, AudioCaptureService]]


def _default_capture_factory() -> CaptureFactory:
    settings = get_settings()
    base = Path(settings.recordings_dir).expanduser()

    def make(meeting_id: str, mode: RecordingMode) -> dict[Stream, AudioCaptureService]:
        # Mic discovery is required in BOTH modes — without it we have no
        # audio to record at all. `find_mic_device` raises `MicDeviceNotFound`
        # which the router maps to `session.no_audio_device`.
        mic_idx = find_mic_device(env_override=settings.mic_device_name)

        if mode == "single":
            # Slice-27 D3: explicitly skip the BlackHole discovery routine
            # in single mode so the env override / hardware state does NOT
            # influence whether the session can start.
            return {
                "me": AudioCaptureService(
                    meeting_id=meeting_id,
                    recordings_dir=base,
                    device_name=mic_idx,
                    stream_label="me",
                ),
            }

        # Dual mode (default) — unchanged from slice-7.
        bh_idx = find_blackhole_device(env_override=settings.blackhole_device_name)
        if bh_idx is None:
            raise NoBlackholeDevice("BlackHole 2ch not detected — see docs/BLACKHOLE_SETUP.md")

        return {
            "me": AudioCaptureService(
                meeting_id=meeting_id,
                recordings_dir=base,
                device_name=mic_idx,
                stream_label="me",
            ),
            "counterparty": AudioCaptureService(
                meeting_id=meeting_id,
                recordings_dir=base,
                device_name=bh_idx,
                stream_label="counterparty",
            ),
        }

    return make


def get_capture_factory_dependency() -> CaptureFactory:
    return _default_capture_factory()


__all__ = [
    "CaptureFactory",
    "RecordingMode",
    "Stream",
    "get_capture_factory_dependency",
]
