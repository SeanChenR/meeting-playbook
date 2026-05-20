"""ASR factory tests — post asr-runtime-extraction (ADR-0027).

Per spec asr-provider-selection MODIFIED requirements:
  * Returns RemoteAsrRuntimeClient instances when meeting.asr_provider is "qwen3"
  * Same (provider_name, stream) returns the same instance (lru_cache)
  * Legacy provider names (whisper, vibevoice, ...) coerce to "qwen3"
    with a structured warning log
  * `ASR_RUNTIME_URL` unset raises AsrRuntimeUnavailableError
"""

from __future__ import annotations

import logging

import pytest

from meeting_playbook.asr import factory
from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.factory import _TraditionalChineseProvider
from meeting_playbook.asr.remote_runtime_client import (
    AsrRuntimeUnavailableError,
    RemoteAsrRuntimeClient,
)


@pytest.fixture(autouse=True)
def _clear_provider_cache(monkeypatch: pytest.MonkeyPatch):
    """Reset the singleton cache between tests + ensure the factory has a
    runtime URL to talk to (tests don't actually hit the network)."""
    monkeypatch.setenv("ASR_RUNTIME_URL", "http://127.0.0.1:8100")
    factory.clear_provider_cache()
    yield
    factory.clear_provider_cache()


def test_qwen3_returns_two_independent_remote_clients() -> None:
    """Canonical provider name → wrapper around RemoteAsrRuntimeClient."""
    me, cp = factory.get_asr_providers_for_meeting("qwen3")
    assert isinstance(me, _TraditionalChineseProvider)
    assert isinstance(cp, _TraditionalChineseProvider)
    assert isinstance(me._inner, RemoteAsrRuntimeClient)
    assert isinstance(cp._inner, RemoteAsrRuntimeClient)
    assert me is not cp, "per-stream providers MUST be independent instances"
    # Wrapper itself satisfies the Protocol.
    assert isinstance(me, ASRProvider)
    assert isinstance(cp, ASRProvider)


def test_factory_caches_per_stream_pair() -> None:
    """Same `(provider_name, stream)` → same instance on the second call."""
    me_a, cp_a = factory.get_asr_providers_for_meeting("qwen3")
    me_b, cp_b = factory.get_asr_providers_for_meeting("qwen3")
    assert me_a is me_b
    assert cp_a is cp_b


def test_legacy_whisper_coerces_to_qwen3(caplog: pytest.LogCaptureFixture) -> None:
    """Legacy `whisper` value is silently routed to the qwen3 remote client
    + a structured warning is emitted so operators see the stale row."""
    with caplog.at_level(logging.WARNING, logger="meeting_playbook.asr.factory"):
        me, cp = factory.get_asr_providers_for_meeting("whisper")
    assert isinstance(me._inner, RemoteAsrRuntimeClient)
    assert isinstance(cp._inner, RemoteAsrRuntimeClient)
    # Structured warning record carries from_value / to_value.
    coerced_records = [r for r in caplog.records if r.message == "asr_provider_coerced"]
    assert coerced_records, "expected a coercion warning"
    assert getattr(coerced_records[0], "from_value") == "whisper"
    assert getattr(coerced_records[0], "to_value") == "qwen3"


def test_unknown_provider_name_coerces_to_qwen3(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Any non-canonical name → coerced to qwen3 with the same warning."""
    with caplog.at_level(logging.WARNING, logger="meeting_playbook.asr.factory"):
        me, _ = factory.get_asr_providers_for_meeting("vibevoice")
    assert isinstance(me._inner, RemoteAsrRuntimeClient)
    coerced_records = [r for r in caplog.records if r.message == "asr_provider_coerced"]
    assert coerced_records
    assert getattr(coerced_records[0], "from_value") == "vibevoice"


def test_runtime_url_unset_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory must surface a clear error if the runtime is not configured —
    backend has no in-process fallback after ADR-0027."""
    monkeypatch.delenv("ASR_RUNTIME_URL", raising=False)
    factory.clear_provider_cache()
    with pytest.raises(AsrRuntimeUnavailableError):
        factory.get_asr_providers_for_meeting("qwen3")
