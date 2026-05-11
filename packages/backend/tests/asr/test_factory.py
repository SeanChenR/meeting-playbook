"""ASR factory tests — slice-11 task 2.1.

Per spec asr-provider-selection ADDED requirement scenarios:
  * Returns Qwen3 instances when meeting.asr_provider is "qwen3"
  * Returns Whisper instances when meeting.asr_provider is "whisper"
  * Same (provider_name, stream) returns the same instance (lru_cache)
  * Unknown provider name falls back to Whisper with a warning log
"""

from __future__ import annotations

import logging

import pytest

from meeting_playbook.asr import factory
from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.factory import _TraditionalChineseProvider
from meeting_playbook.asr.qwen3_provider import Qwen3ASRProvider
from meeting_playbook.asr.whisper_provider import WhisperProvider


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    """Reset the singleton cache between tests so per-test assertions on
    instance identity are deterministic."""
    factory.clear_provider_cache()
    yield
    factory.clear_provider_cache()


def test_qwen3_returns_two_independent_qwen3_instances() -> None:
    me, cp = factory.get_asr_providers_for_meeting("qwen3")
    # Slice-11 fix: every provider is wrapped in _TraditionalChineseProvider
    # so the persisted text is Traditional Chinese (Taiwan). The wrapper
    # forwards the Protocol so callers see ASRProvider semantics.
    assert isinstance(me, _TraditionalChineseProvider)
    assert isinstance(cp, _TraditionalChineseProvider)
    assert isinstance(me._inner, Qwen3ASRProvider)
    assert isinstance(cp._inner, Qwen3ASRProvider)
    assert me is not cp, "per-stream providers MUST be independent instances"
    # Wrapper itself satisfies the Protocol.
    assert isinstance(me, ASRProvider)
    assert isinstance(cp, ASRProvider)


def test_whisper_returns_two_independent_whisper_instances() -> None:
    me, cp = factory.get_asr_providers_for_meeting("whisper")
    assert isinstance(me, _TraditionalChineseProvider)
    assert isinstance(cp, _TraditionalChineseProvider)
    assert isinstance(me._inner, WhisperProvider)
    assert isinstance(cp._inner, WhisperProvider)
    assert me is not cp


def test_repeated_call_returns_same_instances_per_stream() -> None:
    me1, cp1 = factory.get_asr_providers_for_meeting("qwen3")
    me2, cp2 = factory.get_asr_providers_for_meeting("qwen3")
    # Same provider+stream key reuses the cached instance — no double model
    # load on a second meeting that wants the same engine.
    assert me1 is me2
    assert cp1 is cp2


def test_unknown_provider_falls_back_to_whisper_with_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="meeting_playbook.asr.factory"):
        me, cp = factory.get_asr_providers_for_meeting("experimental_xyz")

    assert isinstance(me, _TraditionalChineseProvider)
    assert isinstance(me._inner, WhisperProvider)
    assert isinstance(cp._inner, WhisperProvider)
    assert me is not cp
    assert any(
        "unknown asr_provider" in record.message and "experimental_xyz" in record.message
        for record in caplog.records
    ), f"expected fallback warning; got: {[r.message for r in caplog.records]}"
