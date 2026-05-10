"""Audio device discovery — locate BlackHole + microphone for dual-stream capture.

Per slice-07 design (`Device discovery: name pattern with env override`):
- BlackHole device: any input device whose name contains "BlackHole" and has
  >= 2 input channels. Optional `BLACKHOLE_DEVICE_NAME` env override matches
  by exact name (no substring) when set.
- Microphone device: `sounddevice.default.device[0]` (the system input
  default) unless `MIC_DEVICE_NAME` env override matches by exact name.

Both functions are pure (no side effects beyond `sounddevice.query_devices`)
so the session pre-flight can call them at every WebSocket upgrade without
holding state. They return `int` indices (suitable for `RawInputStream(device=...)`)
or `None`/raise depending on whether the device is required.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def find_blackhole_device(env_override: str | None) -> int | None:
    """Locate the BlackHole input device.

    With `env_override` set, returns the index of the device whose name
    matches exactly. Without override, returns the first device whose name
    contains "BlackHole" and has at least 2 input channels.

    Returns `None` when no matching device exists. Pre-flight uses `None`
    to surface `session.no_blackhole_device` to the client.
    """
    import sounddevice as sd

    devices = sd.query_devices()
    if env_override:
        for idx, dev in enumerate(devices):
            if dev["name"] == env_override and dev["max_input_channels"] > 0:
                logger.info(
                    "BlackHole device resolved via env override: %s (index %d)", env_override, idx
                )
                return idx
        logger.warning(
            "BLACKHOLE_DEVICE_NAME=%r set but no matching input device found", env_override
        )
        return None

    for idx, dev in enumerate(devices):
        if "BlackHole" in dev["name"] and dev["max_input_channels"] >= 2:
            logger.info(
                "BlackHole device auto-detected: %s (index %d, channels=%d)",
                dev["name"],
                idx,
                dev["max_input_channels"],
            )
            return idx
    return None


def find_mic_device(env_override: str | None) -> int:
    """Locate the microphone input device.

    With `env_override` set, returns the index of the input device whose name
    matches exactly. Without override, returns `sounddevice.default.device[0]`.

    Raises `MicDeviceNotFound` when an env override is set but no matching
    device exists. The system default (no override) cannot raise here — if
    the system has no input device at all, the failure surfaces later when
    `RawInputStream(device=...)` is opened.
    """
    import sounddevice as sd

    if env_override:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            if dev["name"] == env_override and dev["max_input_channels"] > 0:
                logger.info(
                    "Mic device resolved via env override: %s (index %d)", env_override, idx
                )
                return idx
        raise MicDeviceNotFound(
            f"MIC_DEVICE_NAME={env_override!r} set but no matching input device found"
        )

    default_in = sd.default.device[0]
    if default_in is None or default_in < 0:
        raise MicDeviceNotFound(
            "no system default input device — set MIC_DEVICE_NAME or check macOS Audio settings"
        )
    logger.info("Mic device resolved via system default: index %d", default_in)
    return int(default_in)


class MicDeviceNotFound(Exception):
    """Raised when `find_mic_device` cannot resolve a microphone."""


class NoBlackholeDevice(Exception):
    """Raised when the BlackHole device is required but cannot be located.

    Surfaces to the WebSocket client as `error_code: session.no_blackhole_device`
    + a link to docs/BLACKHOLE_SETUP.md.
    """


__all__ = [
    "MicDeviceNotFound",
    "NoBlackholeDevice",
    "find_blackhole_device",
    "find_mic_device",
]
