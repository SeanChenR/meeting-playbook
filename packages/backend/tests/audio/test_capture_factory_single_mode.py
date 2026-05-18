"""Capture factory mode-aware behaviour — slice-27.

Per design.md D3 / D9 / Implementation Contract:
- `mode == "single"` MUST NOT call `find_blackhole_device`.
- `mode == "single"` returns a one-entry dict keyed `"me"`.
- `mode == "single"` succeeds even when `BLACKHOLE_DEVICE_NAME` is set but
  no matching device exists (the env var is irrelevant in single mode).
- `mode == "dual"` keeps the legacy two-stream behaviour (regression).

These tests stub `sounddevice.query_devices` (mic discovery still runs in
both modes) and monkey-patch the `find_blackhole_device` helper inside the
factory module so we can assert call-counts without touching real audio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from meeting_playbook.audio.devices import NoBlackholeDevice
from meeting_playbook.sessions import dependencies as deps_mod


@dataclass(frozen=True)
class _StubSettings:
    """Minimal duck-typed stand-in for `Settings` — covers only the attrs
    `_default_capture_factory` reads. Avoids loading real env vars.
    """

    recordings_dir: str
    blackhole_device_name: str | None = None
    mic_device_name: str | None = None


def _patch_settings(monkeypatch, **overrides) -> None:
    """Replace `deps_mod.get_settings` with a 0-arg lambda that returns a
    fresh `_StubSettings` (bypasses the real `lru_cache` indirection).
    """
    monkeypatch.setattr(deps_mod, "get_settings", lambda: _StubSettings(**overrides))


def _stub_sounddevice(monkeypatch, devices, default_input_index: int = 0) -> None:
    """Pretend `sounddevice` has the given devices + the given default input.

    Mirrors the helper in tests/audio/test_devices.py so production
    `find_mic_device` resolves without touching CoreAudio.
    """
    import sounddevice as sd

    monkeypatch.setattr(sd, "query_devices", lambda: devices)
    monkeypatch.setattr(sd, "default", type("D", (), {"device": (default_input_index, 0)})())


@pytest.fixture
def stub_audio_devices(monkeypatch):
    """A working mic + a BlackHole device — the dual-mode happy path baseline."""
    _stub_sounddevice(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "BlackHole 2ch", "max_input_channels": 2},
        ],
        default_input_index=0,
    )


@pytest.fixture
def stub_audio_devices_no_blackhole(monkeypatch):
    """Only a mic; BlackHole physically absent. Single mode MUST still work."""
    _stub_sounddevice(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
        ],
        default_input_index=0,
    )


def test_single_mode_skips_blackhole_lookup(tmp_path: Path, stub_audio_devices, monkeypatch):
    """`mode="single"` MUST NOT consult `find_blackhole_device`.

    Spec scenario "Missing BlackHole device does NOT abort a single-mode
    session" — call count of the BlackHole discovery helper is the
    contract. If a future refactor reintroduces it, this red-flag fires.
    """
    _patch_settings(monkeypatch, recordings_dir=str(tmp_path))

    # Replace the imported `find_blackhole_device` with a counter spy.
    calls: list[None] = []

    def _spy(env_override):
        calls.append(None)
        return 1  # would succeed if invoked

    monkeypatch.setattr(deps_mod, "find_blackhole_device", _spy)

    factory = deps_mod._default_capture_factory()
    result = factory("m_solo", "single")

    assert calls == [], (
        f"find_blackhole_device must NOT be called in single mode; got {len(calls)} call(s)"
    )
    assert set(result.keys()) == {"me"}


def test_single_mode_returns_only_me_entry(tmp_path: Path, stub_audio_devices, monkeypatch):
    """`mode="single"` returns a one-entry dict with `stream_label="me"`."""
    _patch_settings(monkeypatch, recordings_dir=str(tmp_path))

    factory = deps_mod._default_capture_factory()
    result = factory("m_only", "single")

    assert list(result.keys()) == ["me"]
    me_cap = result["me"]
    # `stream_label` is private; check the wav path (which interpolates it).
    assert me_cap.wav_path.name == "me.wav"


def test_single_mode_succeeds_when_blackhole_absent(
    tmp_path: Path, stub_audio_devices_no_blackhole, monkeypatch
):
    """No BlackHole hardware AND a misleading env override — single mode
    MUST still build a working factory result.

    Spec scenario "BLACKHOLE_DEVICE_NAME env override is ignored in single
    mode": even with `BLACKHOLE_DEVICE_NAME` pointed at a ghost, the
    factory should not raise.
    """
    _patch_settings(
        monkeypatch,
        recordings_dir=str(tmp_path),
        blackhole_device_name="BlackHole 16ch",  # ghost device — would normally fail
    )
    factory = deps_mod._default_capture_factory()

    # Must NOT raise NoBlackholeDevice even though BlackHole is absent.
    result = factory("m_ghost", "single")
    assert set(result.keys()) == {"me"}


def test_dual_mode_regression_still_returns_two_entries(
    tmp_path: Path, stub_audio_devices, monkeypatch
):
    """`mode="dual"` keeps the legacy behaviour: two captures, both stream
    labels present, `find_blackhole_device` IS called once.
    """
    _patch_settings(monkeypatch, recordings_dir=str(tmp_path))

    calls: list[None] = []
    original_find = deps_mod.find_blackhole_device

    def _spy(env_override):
        calls.append(None)
        return original_find(env_override)

    monkeypatch.setattr(deps_mod, "find_blackhole_device", _spy)

    factory = deps_mod._default_capture_factory()
    result = factory("m_dual", "dual")

    assert calls == [None], (
        f"dual mode must invoke find_blackhole_device exactly once; got {len(calls)}"
    )
    assert set(result.keys()) == {"me", "counterparty"}
    assert result["me"].wav_path.name == "me.wav"
    assert result["counterparty"].wav_path.name == "counterparty.wav"


def test_dual_mode_missing_blackhole_still_raises_no_blackhole_device(
    tmp_path: Path, stub_audio_devices_no_blackhole, monkeypatch
):
    """Regression: dual mode without BlackHole still raises NoBlackholeDevice,
    so the router-side error-mapping is unchanged.
    """
    _patch_settings(monkeypatch, recordings_dir=str(tmp_path))
    factory = deps_mod._default_capture_factory()
    with pytest.raises(NoBlackholeDevice):
        factory("m_dualfail", "dual")
