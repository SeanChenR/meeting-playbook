"""HTTP `POST /v1/transcribe/chunk` tests (tasks 3.1 / 3.2).

These exercise the route as a black box via `fastapi.testclient.TestClient`.
The Qwen3Runner instance is monkeypatched so we don't load the real model.
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
    """Bypass model load entirely + record whether we were asked to fail."""

    def __init__(self, *, should_raise: bool = False) -> None:
        # Skip super().__init__ to avoid triggering the qwen-asr import
        # path — but populate the attrs the parent class' properties read.
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


def test_transcribe_http_success(_success_client: TestClient) -> None:
    """POST a silent chunk → 200 with text + started_at + ended_at."""
    silent = bytes(16000 * 2 * 1)
    resp = _success_client.post(
        "/v1/transcribe/chunk",
        json={
            "audio_bytes_b64": encode_pcm_bytes(silent),
            "sample_rate_hz": 16000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == ""
    assert "started_at" in body
    assert "ended_at" in body


def test_transcribe_http_runtime_error_shape(_failing_client: TestClient) -> None:
    """Runner exception → HTTP 503 + structured error envelope."""
    silent = bytes(16000 * 2 * 1)
    resp = _failing_client.post(
        "/v1/transcribe/chunk",
        json={
            "audio_bytes_b64": encode_pcm_bytes(silent),
            "sample_rate_hz": 16000,
        },
    )
    assert resp.status_code == 503
    body = resp.json()
    assert body["error_code"] == "asr.runtime_unavailable"
    assert "message" in body
    assert body["retriable"] is False


def test_transcribe_http_rejects_malformed_base64(_success_client: TestClient) -> None:
    """Garbage in the base64 field → 503 with the same envelope shape."""
    resp = _success_client.post(
        "/v1/transcribe/chunk",
        json={"audio_bytes_b64": "!!!not-base64!!!", "sample_rate_hz": 16000},
    )
    assert resp.status_code == 503
    assert resp.json()["error_code"] == "asr.runtime_unavailable"
