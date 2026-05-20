"""WebSocket `/v1/transcribe/stream` tests (tasks 4.1 / 4.2).

`fastapi.testclient.TestClient` provides a synchronous WebSocket client
that's enough to exercise the handshake → audio_chunk → transcript_chunk
loop. The Qwen3Runner is monkeypatched (same stub style as the HTTP tests)
so we don't load real model weights.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from meeting_playbook_asr_runtime import server as server_module
from meeting_playbook_asr_runtime.qwen3_runner import Qwen3Runner, TranscriptChunk
from meeting_playbook_asr_runtime.schemas import encode_pcm_bytes


from meeting_playbook_asr_runtime.qwen3_runner import Qwen3Config


class _StubRunner(Qwen3Runner):
    def __init__(self, *, should_raise: bool = False) -> None:
        self._config = Qwen3Config()
        self._model = object()
        self._should_raise = should_raise

    async def load(self) -> None:  # type: ignore[override]
        return None

    async def transcribe(  # type: ignore[override]
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk:
        if self._should_raise:
            raise RuntimeError("stub: model crashed")
        now = datetime.now(UTC)
        return TranscriptChunk(text="", started_at=now, ended_at=now)


@pytest.fixture
def _success_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(server_module, "_get_runner", lambda: _StubRunner())
    with TestClient(server_module.app) as client:
        yield client


@pytest.fixture
def _failing_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(server_module, "_get_runner", lambda: _StubRunner(should_raise=True))
    with TestClient(server_module.app) as client:
        yield client


def test_ws_handshake_then_transcribe_chunk(_success_client: TestClient) -> None:
    """config → ready → audio_chunk → transcript_chunk with matching sequence."""
    silent = bytes(16000 * 2 * 1)
    with _success_client.websocket_connect("/v1/transcribe/stream") as ws:
        ws.send_json({"type": "config", "sample_rate_hz": 16000})
        first = ws.receive_json()
        assert first == {"type": "ready"}
        ws.send_json(
            {
                "type": "audio_chunk",
                "sequence": 42,
                "audio_bytes_b64": encode_pcm_bytes(silent),
            }
        )
        result = ws.receive_json()
        assert result["type"] == "transcript_chunk"
        assert result["sequence"] == 42
        assert result["text"] == ""
        assert "started_at" in result
        assert "ended_at" in result


def test_ws_error_closes_connection(_failing_client: TestClient) -> None:
    """Runner raise → error frame, then socket closes."""
    from starlette.websockets import WebSocketDisconnect

    silent = bytes(16000 * 2 * 1)
    with _failing_client.websocket_connect("/v1/transcribe/stream") as ws:
        ws.send_json({"type": "config", "sample_rate_hz": 16000})
        ready = ws.receive_json()
        assert ready == {"type": "ready"}
        ws.send_json(
            {
                "type": "audio_chunk",
                "sequence": 1,
                "audio_bytes_b64": encode_pcm_bytes(silent),
            }
        )
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["error_code"] == "asr.runtime_unavailable"
        # Next receive SHALL raise — server closed the socket cleanly.
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
