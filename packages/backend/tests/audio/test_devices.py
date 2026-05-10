"""Device-discovery unit tests using monkeypatched sounddevice.query_devices.

Per slice-07 design (`Device discovery: name pattern with env override`).
These tests run anywhere — no real device required.
"""

from __future__ import annotations

import pytest

from meeting_playbook.audio.devices import (
    MicDeviceNotFound,
    find_blackhole_device,
    find_mic_device,
)


def _stub_devices(monkeypatch, devices, default_input_index=0):
    """Patch sounddevice.query_devices + sounddevice.default to return canned data."""
    import sounddevice as sd

    monkeypatch.setattr(sd, "query_devices", lambda: devices)
    # sd.default.device is a sequence (input_idx, output_idx)
    monkeypatch.setattr(sd, "default", type("D", (), {"device": (default_input_index, 0)})())


def test_find_blackhole_returns_index_when_name_pattern_matches(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "BlackHole 2ch", "max_input_channels": 2},
            {"name": "MacBook Pro Speakers", "max_input_channels": 0},
        ],
    )
    assert find_blackhole_device(env_override=None) == 1


def test_find_blackhole_returns_none_when_missing(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "MacBook Pro Speakers", "max_input_channels": 0},
        ],
    )
    assert find_blackhole_device(env_override=None) is None


def test_find_blackhole_skips_devices_with_too_few_channels(monkeypatch):
    """A device named BlackHole but with 0 input channels MUST NOT match."""
    _stub_devices(
        monkeypatch,
        [
            {"name": "BlackHole 2ch", "max_input_channels": 0},  # output-only
            {"name": "BlackHole 16ch", "max_input_channels": 16},
        ],
    )
    assert find_blackhole_device(env_override=None) == 1


def test_find_blackhole_env_override_exact_match(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "BlackHole 2ch", "max_input_channels": 2},
            {"name": "BlackHole 16ch", "max_input_channels": 16},
        ],
    )
    # Override picks the second device by exact name.
    assert find_blackhole_device(env_override="BlackHole 16ch") == 1


def test_find_blackhole_env_override_returns_none_when_no_match(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "BlackHole 2ch", "max_input_channels": 2},
        ],
    )
    assert find_blackhole_device(env_override="Nonexistent Device") is None


def test_find_mic_returns_system_default_when_no_override(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "Sean Microphone", "max_input_channels": 1},
        ],
        default_input_index=1,
    )
    assert find_mic_device(env_override=None) == 1


def test_find_mic_env_override_picks_named_device(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "Sean Microphone", "max_input_channels": 1},
        ],
        default_input_index=0,
    )
    assert find_mic_device(env_override="Sean Microphone") == 1


def test_find_mic_env_override_raises_when_missing(monkeypatch):
    _stub_devices(
        monkeypatch,
        [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
        ],
    )
    with pytest.raises(MicDeviceNotFound):
        find_mic_device(env_override="Ghost Mic")
