"""FastAPI dependencies for the sessions router (slice-07: dual-stream).

Tests override these with stubs (mock provider map, mock capture map factory).
Production wires:
- One `WhisperProvider` instance per stream so model inference can run in
  parallel without serialising at the lock level (per design.md
  `ASR concurrency: two WhisperProvider instances with parallel warmup`).
- A capture factory that resolves the BlackHole + microphone devices via
  `find_blackhole_device` / `find_mic_device` (with env-var overrides) and
  returns one `AudioCaptureService` per stream. If BlackHole is not present
  the factory raises `NoBlackholeDevice` which the router converts into an
  `error_code: session.no_blackhole_device` frame.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Literal

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.whisper_provider import WhisperProvider
from meeting_playbook.audio.capture import AudioCaptureService
from meeting_playbook.audio.devices import (
    NoBlackholeDevice,
    find_blackhole_device,
    find_mic_device,
)
from meeting_playbook.config import get_settings

Stream = Literal["me", "counterparty"]


@lru_cache
def _whisper_singleton_me() -> WhisperProvider:
    return WhisperProvider()


@lru_cache
def _whisper_singleton_counterparty() -> WhisperProvider:
    return WhisperProvider()


def get_asr_providers_dependency() -> dict[Stream, ASRProvider]:
    """Per-stream ASR providers — separate WhisperProvider instances so warmup
    + inference run in parallel (different model objects)."""
    return {
        "me": _whisper_singleton_me(),
        "counterparty": _whisper_singleton_counterparty(),
    }


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


# ─── Slice-6 backward-compat shim ─────────────────────────────────
# A few callers (server.py wiring tests, possibly external) still imported
# `get_asr_provider_dependency` (singular). Keep it returning the `me`
# provider so any straggler import doesn't break.


def get_asr_provider_dependency() -> ASRProvider:
    """Slice-6 compat shim — returns the `me` stream's provider."""
    return _whisper_singleton_me()


__all__ = [
    "CaptureFactory",
    "Stream",
    "get_asr_provider_dependency",
    "get_asr_providers_dependency",
    "get_capture_factory_dependency",
]
