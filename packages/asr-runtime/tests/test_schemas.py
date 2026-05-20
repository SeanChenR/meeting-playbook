"""Schema helpers — base64 PCM encode/decode round-trip (task 2.3)."""

from __future__ import annotations

import pytest

from meeting_playbook_asr_runtime.schemas import decode_pcm_bytes, encode_pcm_bytes


@pytest.mark.parametrize(
    "payload",
    [
        bytes(),
        b"\x00" * 64,
        bytes(range(256)),
        bytes(16000 * 2 * 1),  # 1s of silent 16kHz int16 PCM
    ],
)
def test_pcm_roundtrip(payload: bytes) -> None:
    """encode → decode SHALL be lossless for any byte payload."""
    encoded = encode_pcm_bytes(payload)
    assert isinstance(encoded, str)
    decoded = decode_pcm_bytes(encoded)
    assert decoded == payload


def test_decode_rejects_malformed_payload() -> None:
    """Garbage in → ValueError, not a silent truncation."""
    with pytest.raises(ValueError, match="invalid base64"):
        decode_pcm_bytes("!!!not-base64!!!")
