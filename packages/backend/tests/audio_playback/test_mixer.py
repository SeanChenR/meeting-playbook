"""Unit tests for mixer module — slice-25 task 1.1 + 1.3.

Per spec audio-playback ADDED requirements:
  - "mix_pcm_int16 averages two equal-length int16 PCM byte buffers without overflow"
  - "ensure_mixed_wav is lazy, idempotent, and zero-pads the shorter stream"
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

# ─── mix_pcm_int16 (task 1.1) ─────────────────────────────────────────


def test_mix_two_silent_buffers_returns_silence():
    from meeting_playbook.audio_playback.mixer import mix_pcm_int16

    silence = bytes(8000)  # 4000 int16 zero samples
    result = mix_pcm_int16(silence, silence)
    assert result == silence
    assert len(result) == 8000


def test_mix_plus_minus_constants_yields_zero():
    from meeting_playbook.audio_playback.mixer import mix_pcm_int16

    left = np.full(100, 1000, dtype=np.int16).tobytes()
    right = np.full(100, -1000, dtype=np.int16).tobytes()
    result = np.frombuffer(mix_pcm_int16(left, right), dtype=np.int16)
    assert result.shape == (100,)
    assert (result == 0).all()


def test_mix_max_amplitudes_does_not_overflow():
    """+32767 + +32767 must not wrap to negative — design D2 guarantees no overflow."""
    from meeting_playbook.audio_playback.mixer import mix_pcm_int16

    left = np.full(100, 32767, dtype=np.int16).tobytes()
    right = np.full(100, 32767, dtype=np.int16).tobytes()
    result = np.frombuffer(mix_pcm_int16(left, right), dtype=np.int16)
    assert result.shape == (100,)
    assert (result == 32767).all()  # NOT negative wrap-around


def test_mismatched_length_raises_value_error():
    from meeting_playbook.audio_playback.mixer import mix_pcm_int16

    with pytest.raises(ValueError):
        mix_pcm_int16(bytes(8000), bytes(4000))


# ─── ensure_mixed_wav (task 1.3) ──────────────────────────────────────


def _write_mono_wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    """Helper — write a mono 16-bit PCM WAV at the given sample rate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.astype(np.int16).tobytes())


def test_ensure_mix_first_call_writes_then_second_call_returns_cached_path(tmp_path):
    from meeting_playbook.audio_playback.mixer import ensure_mixed_wav

    meeting_dir = tmp_path / "m_x"
    _write_mono_wav(meeting_dir / "me.wav", np.full(1000, 100, dtype=np.int16))
    _write_mono_wav(meeting_dir / "counterparty.wav", np.full(1000, 300, dtype=np.int16))

    mixed_path = ensure_mixed_wav("m_x", tmp_path)
    assert mixed_path == meeting_dir / "mixed.wav"
    assert mixed_path.exists()
    first_mtime = mixed_path.stat().st_mtime_ns

    # Second call — file must not be rewritten.
    mixed_path_again = ensure_mixed_wav("m_x", tmp_path)
    assert mixed_path_again == mixed_path
    assert mixed_path.stat().st_mtime_ns == first_mtime


def test_ensure_mix_missing_me_raises_mixer_input_missing(tmp_path):
    from meeting_playbook.audio_playback.mixer import (
        MixerInputMissing,
        ensure_mixed_wav,
    )

    meeting_dir = tmp_path / "m_y"
    _write_mono_wav(meeting_dir / "counterparty.wav", np.full(1000, 300, dtype=np.int16))
    # no me.wav

    with pytest.raises(MixerInputMissing):
        ensure_mixed_wav("m_y", tmp_path)
    assert not (meeting_dir / "mixed.wav").exists()


def test_ensure_mix_shorter_side_zero_padded(tmp_path):
    """Per spec scenario — me=1000@+5000, them=500@+3000 → 1000 samples total."""
    from meeting_playbook.audio_playback.mixer import ensure_mixed_wav

    meeting_dir = tmp_path / "m_z"
    _write_mono_wav(meeting_dir / "me.wav", np.full(1000, 5000, dtype=np.int16))
    _write_mono_wav(meeting_dir / "counterparty.wav", np.full(500, 3000, dtype=np.int16))

    mixed_path = ensure_mixed_wav("m_z", tmp_path)
    with wave.open(str(mixed_path), "rb") as r:
        assert r.getnchannels() == 1
        assert r.getframerate() == 16000
        assert r.getsampwidth() == 2
        assert r.getnframes() == 1000
        pcm = np.frombuffer(r.readframes(1000), dtype=np.int16)

    # First 500: (5000 + 3000) // 2 = 4000
    assert (pcm[:500] == 4000).all()
    # Last 500: them was zero-padded → (5000 + 0) // 2 = 2500
    assert (pcm[500:] == 2500).all()
