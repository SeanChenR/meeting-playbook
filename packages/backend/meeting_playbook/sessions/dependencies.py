"""FastAPI dependencies for the sessions router.

Slice-11 dropped the per-stream `_whisper_singleton_*` lru_cache + the
`get_asr_providers_dependency` Depends; ASR provider selection is now done
inside the WebSocket handler via `meeting_playbook.asr.factory.
get_asr_providers_for_meeting(meeting.asr_provider)` so it can branch on
the per-meeting engine choice (FastAPI dependencies resolve before the path
parameter is loaded, which is too early to know which engine to build).

What's left here (slice-7):
- `CaptureFactory` resolves the BlackHole + microphone devices via
  `find_blackhole_device` / `find_mic_device` (with env-var overrides) and
  returns one `AudioCaptureService` per stream. If BlackHole is not present
  the factory raises `NoBlackholeDevice` which the router converts into an
  `error_code: session.no_blackhole_device` frame.
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


# Slice-7: factory returns BOTH stream captures (resolves devices internally
# and raises NoBlackholeDevice on missing BlackHole — router maps to error code).
CaptureFactory = Callable[[str], dict[Stream, AudioCaptureService]]


def _default_capture_factory() -> CaptureFactory:
    settings = get_settings()
    base = Path(settings.recordings_dir).expanduser()

    def make(meeting_id: str) -> dict[Stream, AudioCaptureService]:
        bh_idx = find_blackhole_device(env_override=settings.blackhole_device_name)
        if bh_idx is None:
            raise NoBlackholeDevice("BlackHole 2ch not detected — see docs/BLACKHOLE_SETUP.md")
        mic_idx = find_mic_device(env_override=settings.mic_device_name)

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
    "Stream",
    "get_capture_factory_dependency",
]
