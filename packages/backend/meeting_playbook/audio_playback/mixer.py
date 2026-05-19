"""Mix two mono PCM streams into a single mono stream — slice-25 design D1+D2.

The meeting recording layer captures BlackHole (對方) and microphone (我方) as
two independent mono WAV files (`{recordings_dir}/{meeting_id}/{counterparty|me}.wav`).
This module produces a server-side mix so the meeting detail audio player can
present a single combined stream — playing only one side made the counterparty
inaudible (see proposal Why).

Design references:
  - D1: server-side mix, not client-side
  - D2: sample-by-sample averaging in int32 then truncate to int16 (no overflow)
  - D3: lazy compute on first range request; idempotent via tmp + atomic rename
  - D7: missing input is treated as 'not applicable' for single-channel meetings
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np

__all__ = [
    "MixerError",
    "MixerInputMissing",
    "ensure_mixed_wav",
    "mix_pcm_int16",
]


class MixerError(Exception):
    """Base class for mixer failures so the router can map to error envelopes."""


class MixerInputMissing(MixerError):
    """Raised when either me.wav or counterparty.wav is absent — single-channel meeting."""


def mix_pcm_int16(left: bytes, right: bytes) -> bytes:
    """Sample-by-sample mean of two equal-length 16-bit signed PCM byte buffers.

    Computation runs in int32 to keep the intermediate sum within range, then
    truncates back to int16. Because ``(int16_max + int16_max) // 2 ==
    int16_max`` (and the symmetric negative case), the result NEVER overflows
    int16 — no clamp is needed.

    Raises ``ValueError`` when the two buffers differ in length. Callers
    (``ensure_mixed_wav``) MUST zero-pad before invoking.
    """
    if len(left) != len(right):
        raise ValueError(
            f"mix_pcm_int16 requires equal-length buffers; "
            f"got len(left)={len(left)} len(right)={len(right)}",
        )
    if not left:
        return b""
    L = np.frombuffer(left, dtype=np.int16).astype(np.int32)
    R = np.frombuffer(right, dtype=np.int16).astype(np.int32)
    mixed = ((L + R) // 2).astype(np.int16)
    return mixed.tobytes()


def ensure_mixed_wav(meeting_id: str, recordings_dir: Path) -> Path:
    """Lazy + idempotent: produce ``{recordings_dir}/{meeting_id}/mixed.wav``.

    Behavior per design D3:
      1. If ``mixed.wav`` already exists, return its path without rewriting.
      2. If ``me.wav`` or ``counterparty.wav`` is missing, raise ``MixerInputMissing``
         (handler maps to HTTP 404 ``recording.mixed_not_applicable``).
      3. Otherwise read both PCM data sections, zero-pad the shorter side to
         the longer length (with int16 silence ``0x0000``), call
         ``mix_pcm_int16``, write to ``mixed.wav.tmp``, then ``os.rename``
         to ``mixed.wav`` (atomic last-writer-wins under concurrency).

    Output WAV mirrors the input format: mono, 16 kHz, 16-bit PCM — so the
    existing ``parse_wav_header`` validation passes (which still rejects
    stereo).
    """
    meeting_dir = recordings_dir / meeting_id
    mixed_path = meeting_dir / "mixed.wav"
    if mixed_path.exists():
        return mixed_path

    me_path = meeting_dir / "me.wav"
    counterparty_path = meeting_dir / "counterparty.wav"
    if not me_path.exists() or not counterparty_path.exists():
        raise MixerInputMissing(
            f"Meeting {meeting_id} is not dual-channel: "
            f"me.wav={'present' if me_path.exists() else 'missing'}, "
            f"counterparty.wav={'present' if counterparty_path.exists() else 'missing'}",
        )

    me_pcm, frame_rate = _read_pcm_data(me_path)
    counterparty_pcm, counterparty_rate = _read_pcm_data(counterparty_path)
    if frame_rate != counterparty_rate:
        raise MixerError(
            f"Meeting {meeting_id}: sample rate mismatch "
            f"(me={frame_rate}Hz, counterparty={counterparty_rate}Hz)",
        )

    target_len = max(len(me_pcm), len(counterparty_pcm))
    me_padded = me_pcm.ljust(target_len, b"\x00")
    counterparty_padded = counterparty_pcm.ljust(target_len, b"\x00")
    mixed_pcm = mix_pcm_int16(me_padded, counterparty_padded)

    tmp_path = mixed_path.with_suffix(".wav.tmp")
    try:
        with wave.open(str(tmp_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(frame_rate)
            w.writeframes(mixed_pcm)
        os.replace(tmp_path, mixed_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return mixed_path


def _read_pcm_data(wav_path: Path) -> tuple[bytes, int]:
    """Return (raw PCM bytes, frame_rate) from a mono 16-bit WAV.

    Wraps ``wave.Error`` (corrupt header, EOF mid-chunk, etc.) as ``MixerError``
    so the router's single except branch covers it.
    """
    try:
        with wave.open(str(wav_path), "rb") as r:
            if r.getnchannels() != 1 or r.getsampwidth() != 2:
                raise MixerError(
                    f"Unexpected WAV format at {wav_path}: "
                    f"channels={r.getnchannels()}, sampwidth={r.getsampwidth()}",
                )
            nframes = r.getnframes()
            return r.readframes(nframes), r.getframerate()
    except wave.Error as e:
        raise MixerError(f"Failed to parse WAV at {wav_path}: {e}") from e
