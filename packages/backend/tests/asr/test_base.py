"""ASRProvider Protocol + TranscriptChunk dataclass shape — slice-06.

Per spec meeting-session ADDED requirement "ASRProvider interface enables
multiple ASR engines (per ADR-0005)".
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timezone

import pytest

from meeting_playbook.asr.base import ASRProvider, TranscriptChunk


def test_transcript_chunk_is_frozen_dataclass_with_expected_fields():
    assert dataclasses.is_dataclass(TranscriptChunk)
    # frozen=True forbids attribute assignment
    chunk = TranscriptChunk(
        text="hello",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        asr_provider_used="whisper",
        confidence=0.9,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.text = "mutated"  # type: ignore[misc]

    field_names = {f.name for f in dataclasses.fields(TranscriptChunk)}
    assert field_names == {
        "text",
        "started_at",
        "ended_at",
        "asr_provider_used",
        "confidence",
    }


def test_asr_provider_protocol_declares_name_and_transcribe_chunk():
    # Protocol membership is structural; assert the attribute names are present
    # on the class definition.
    assert hasattr(ASRProvider, "name")
    assert hasattr(ASRProvider, "transcribe_chunk")

    sig = inspect.signature(ASRProvider.transcribe_chunk)
    params = list(sig.parameters)
    assert params == ["self", "audio_bytes", "sample_rate_hz", "language_hint"]
    assert sig.parameters["language_hint"].default is None


def test_asr_provider_is_runtime_checkable_protocol():
    # A duck-typed instance with the right attributes satisfies the Protocol
    # at runtime so DI can validate without a registry.
    class _Stub:
        @property
        def name(self) -> str:
            return "stub"

        async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):  # type: ignore[no-untyped-def]
            return None

    assert isinstance(_Stub(), ASRProvider)
