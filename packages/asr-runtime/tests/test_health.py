"""`GET /healthz` + lifespan warmup tests (tasks 5.1 / 5.2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from meeting_playbook_asr_runtime import server as server_module
from meeting_playbook_asr_runtime.qwen3_runner import (
    Qwen3Config,
    Qwen3Runner,
    TranscriptChunk,
)


class _StubRunner(Qwen3Runner):
    """Track load() invocations without touching the upstream model."""

    def __init__(self, *, raise_on_load: bool = False) -> None:
        # Skip super().__init__ to avoid triggering qwen-asr import path —
        # but populate the same attributes the parent class exposes so the
        # `model_repo` / `device` property accessors still work.
        self._config = Qwen3Config()
        self._model = object()  # any non-None sentinel
        self._raise_on_load = raise_on_load
        self.load_calls = 0

    async def load(self) -> None:  # type: ignore[override]
        self.load_calls += 1
        if self._raise_on_load:
            raise RuntimeError("stub: cold-start failed")

    async def transcribe(  # type: ignore[override]
        self, _audio_bytes: bytes, sample_rate_hz: int, language_hint: str | None = None
    ) -> TranscriptChunk:
        # Return a no-op chunk so the lifespan's silent warmup pass doesn't
        # blow up. Tests assert on `_runtime_state.status` + `load_calls`,
        # never on transcript content here.
        now = datetime.now(UTC)
        return TranscriptChunk(text="", started_at=now, ended_at=now)


@pytest.fixture(autouse=True)
def _isolate_runtime_state() -> Iterator[None]:
    """Reset the module-level singleton + status between tests so the
    lifespan-driven state transitions are observable."""
    server_module._runner = None
    server_module._runtime_state.reset()
    yield
    server_module._runner = None
    server_module._runtime_state.reset()


def test_healthz_ready_after_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ASR_RUNTIME_WARMUP_ON_BOOT=1` → status flips to `ready` after lifespan startup."""
    stub = _StubRunner()
    monkeypatch.setattr(server_module, "_get_runner", lambda: stub)
    monkeypatch.setenv("ASR_RUNTIME_WARMUP_ON_BOOT", "1")
    with TestClient(server_module.app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["model_repo"]  # non-empty
        assert body["device"]  # non-empty
        assert body["uptime_seconds"] >= 0
    assert stub.load_calls >= 1


def test_healthz_loading_when_warmup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ASR_RUNTIME_WARMUP_ON_BOOT=0` → status stays `loading` until first real call.

    Verifies the env flag actually short-circuits the warmup branch. The
    runtime intentionally stays in `loading` until the first transcribe
    request triggers a lazy load (per design Decision 5).
    """
    stub = _StubRunner()
    monkeypatch.setattr(server_module, "_get_runner", lambda: stub)
    monkeypatch.setenv("ASR_RUNTIME_WARMUP_ON_BOOT", "0")
    with TestClient(server_module.app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "loading"
    assert stub.load_calls == 0


def test_healthz_error_when_warmup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warmup raise → status `error` + `last_error` populated."""
    stub = _StubRunner(raise_on_load=True)
    monkeypatch.setattr(server_module, "_get_runner", lambda: stub)
    monkeypatch.setenv("ASR_RUNTIME_WARMUP_ON_BOOT", "1")
    with TestClient(server_module.app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert "last_error" in body
        assert "cold-start" in body["last_error"]
