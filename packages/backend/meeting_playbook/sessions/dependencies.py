"""FastAPI dependencies for the sessions router.

Tests override these with stubs (mock ASR provider, mock capture factory).
Production wires the real WhisperProvider + AudioCaptureService.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.whisper_provider import WhisperProvider
from meeting_playbook.audio.capture import AudioCaptureService
from meeting_playbook.config import get_settings


@lru_cache
def _whisper_singleton() -> WhisperProvider:
    return WhisperProvider()


def get_asr_provider_dependency() -> ASRProvider:
    return _whisper_singleton()


CaptureFactory = Callable[[str], AudioCaptureService]


def _default_capture_factory() -> CaptureFactory:
    settings = get_settings()
    base = Path(settings.recordings_dir).expanduser()

    def make(meeting_id: str) -> AudioCaptureService:
        return AudioCaptureService(meeting_id=meeting_id, recordings_dir=base)

    return make


def get_capture_factory_dependency() -> CaptureFactory:
    return _default_capture_factory()


__all__ = [
    "CaptureFactory",
    "get_asr_provider_dependency",
    "get_capture_factory_dependency",
]
