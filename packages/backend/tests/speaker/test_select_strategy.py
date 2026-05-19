"""Behavioural tests for `select_strategy`.

Verifies the four scenarios from spec requirement
"select_strategy chooses dual or single based on recording configuration":
- two recordings with `{me, counterparty}` → DualChannelStrategy
- single recording → SingleChannelStrategy
- two recordings with mismatched stream values → InvalidSpeakerConfiguration
- three recordings → InvalidSpeakerConfiguration
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from meeting_playbook.sessions.models import Recording
from meeting_playbook.speaker.diarization import (
    DiarizationProviderUnavailable,
    DiarizationSegment,
)
from meeting_playbook.speaker.strategy import (
    DualChannelStrategy,
    InvalidSpeakerConfiguration,
    SingleChannelStrategy,
    select_strategy,
)


def _recording(stream: str, *, id_: str | None = None) -> Recording:
    return Recording(
        id=id_ or f"rec_{stream}",
        meeting_id="m_test",
        stream=stream,
        file_path=f"/tmp/{stream}.wav",
        bytes=0,
        created_at=datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC),
    )


class _StubProvider:
    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        return []


def test_dual_channel_recording_pair_returns_dual_channel_strategy() -> None:
    recordings = [_recording("me"), _recording("counterparty")]

    strategy = select_strategy(recordings)

    assert isinstance(strategy, DualChannelStrategy)


def test_dual_channel_order_does_not_matter() -> None:
    """Order-independence: {counterparty, me} also picks DualChannelStrategy."""
    recordings = [_recording("counterparty"), _recording("me")]

    strategy = select_strategy(recordings)

    assert isinstance(strategy, DualChannelStrategy)


def test_single_recording_returns_single_channel_strategy_with_injected_provider() -> None:
    provider = _StubProvider()
    recordings = [_recording("me")]

    strategy = select_strategy(recordings, single_channel_provider=provider)

    assert isinstance(strategy, SingleChannelStrategy)
    assert strategy.provider is provider


def test_two_recordings_with_mismatched_streams_raise_invalid_configuration() -> None:
    recordings = [_recording("me", id_="rec_a"), _recording("me", id_="rec_b")]

    with pytest.raises(InvalidSpeakerConfiguration) as excinfo:
        select_strategy(recordings)

    assert "me" in str(excinfo.value).lower()


def test_three_recordings_raise_invalid_configuration() -> None:
    recordings = [_recording("me"), _recording("counterparty"), _recording("extra")]

    with pytest.raises(InvalidSpeakerConfiguration) as excinfo:
        select_strategy(recordings)

    assert "3" in str(excinfo.value) or "got 3" in str(excinfo.value)


def test_zero_recordings_raise_invalid_configuration() -> None:
    with pytest.raises(InvalidSpeakerConfiguration):
        select_strategy([])


def test_default_provider_returns_pyannote_when_token_present(monkeypatch) -> None:
    """With PYANNOTE_AUTH_TOKEN set, the default DiarizationProvider is
    PyannoteProvider — verified through the returned SingleChannelStrategy.
    """
    from meeting_playbook import config
    from meeting_playbook.speaker.pyannote_provider import PyannoteProvider

    config.get_settings.cache_clear()
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", "tok_xyz")

    strategy = select_strategy([_recording("mic")])

    assert isinstance(strategy, SingleChannelStrategy)
    assert isinstance(strategy.provider, PyannoteProvider)
    config.get_settings.cache_clear()


def test_default_provider_raises_when_token_missing(monkeypatch) -> None:
    """Without PYANNOTE_AUTH_TOKEN, select_strategy fails loud with a message
    pointing at the missing environment variable. No degraded fallback.
    """
    from meeting_playbook import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("PYANNOTE_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", "")

    with pytest.raises(DiarizationProviderUnavailable) as excinfo:
        select_strategy([_recording("mic")])

    assert "PYANNOTE_AUTH_TOKEN" in str(excinfo.value)
    config.get_settings.cache_clear()


# ───── SPEAKER_HYBRID_ENABLED rollback flag (slice-12 Task 5.3) ──────


def test_hybrid_disabled_rejects_single_channel_configuration(monkeypatch) -> None:
    """With SPEAKER_HYBRID_ENABLED=false, single-channel configurations
    SHALL raise InvalidSpeakerConfiguration regardless of provider injection.
    """
    from meeting_playbook import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SPEAKER_HYBRID_ENABLED", "false")
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", "tok_xyz")  # would otherwise succeed

    with pytest.raises(InvalidSpeakerConfiguration) as excinfo:
        select_strategy([_recording("me")], single_channel_provider=_StubProvider())

    assert "SPEAKER_HYBRID_ENABLED" in str(excinfo.value)
    config.get_settings.cache_clear()


def test_hybrid_disabled_still_allows_dual_channel(monkeypatch) -> None:
    """The kill switch only disables single-channel; dual-channel keeps
    working so users can fall back to pre-slice-12 behaviour.
    """
    from meeting_playbook import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SPEAKER_HYBRID_ENABLED", "false")

    strategy = select_strategy([_recording("me"), _recording("counterparty")])

    assert isinstance(strategy, DualChannelStrategy)
    config.get_settings.cache_clear()


def test_hybrid_enabled_default_allows_single_channel(monkeypatch) -> None:
    """Default (no env override) keeps SPEAKER_HYBRID_ENABLED=True — sanity check."""
    from meeting_playbook import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("SPEAKER_HYBRID_ENABLED", raising=False)

    strategy = select_strategy([_recording("me")], single_channel_provider=_StubProvider())

    assert isinstance(strategy, SingleChannelStrategy)
    config.get_settings.cache_clear()
