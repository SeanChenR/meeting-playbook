"""RemoteAsrRuntimeClient — backend-side ASRProvider that proxies to the
standalone asr-runtime micro-service.

The standalone runtime owns the Qwen3-ASR model; this client just forwards
audio chunks over HTTP / WebSocket and re-shapes the response into the
`TranscriptChunk` dataclass the session router already speaks. Per ADR-0027,
this is the only ASR provider the backend ships now — the in-process MLX /
Whisper providers have been retired.

The error contract is fixed: any non-2xx response, malformed body, or
runtime `error_code: asr.runtime_unavailable` is re-raised as
`AsrRuntimeUnavailableError`. The session router translates that into a
WebSocket error frame; offline ingest retries with exponential backoff.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import UTC, datetime

import httpx

from meeting_playbook.asr.base import TranscriptChunk

logger = logging.getLogger(__name__)


class AsrRuntimeUnavailableError(RuntimeError):
    """Raised by the client whenever the asr-runtime micro-service cannot
    service a request. Carries the structured `error_code` and a hint at
    whether the failure is retriable so offline ingest can decide whether
    to back off + retry."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "asr.runtime_unavailable",
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.retriable = retriable


class RemoteAsrRuntimeClient:
    """`ASRProvider` impl backed by HTTP POSTs against asr-runtime.

    The class is intentionally simple — one `httpx.AsyncClient` per stream
    instance, no connection pooling tricks, all retries deferred to the
    caller (session router / offline ingest). Keeps the failure semantics
    obvious.
    """

    def __init__(
        self,
        stream: str,
        runtime_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        warmup_timeout_s: float = 60.0,
        warmup_poll_interval_s: float = 1.0,
        request_timeout_s: float = 30.0,
    ) -> None:
        if not runtime_url:
            runtime_url = os.environ.get("ASR_RUNTIME_URL")
        if not runtime_url:
            raise AsrRuntimeUnavailableError(
                "ASR_RUNTIME_URL is not set — backend cannot reach the asr-runtime "
                "service. Start it via the root dev script or set the env var."
            )
        self._stream = stream
        self._runtime_url = runtime_url.rstrip("/")
        self._warmup_timeout_s = warmup_timeout_s
        self._warmup_poll_interval_s = warmup_poll_interval_s
        self._client = httpx.AsyncClient(
            base_url=self._runtime_url,
            timeout=request_timeout_s,
            transport=transport,
        )

    @property
    def name(self) -> str:
        # The `asr_provider_used` value persisted into transcript_chunk rows.
        # Even though the actual model lives in the runtime, callers still
        # think of this as the "qwen3" provider — keep the label consistent
        # with the meeting.asr_provider column.
        return "qwen3"

    async def warmup(self) -> None:
        """Poll `/healthz` until the runtime reports `status: ready`."""
        deadline = asyncio.get_event_loop().time() + self._warmup_timeout_s
        while True:
            try:
                resp = await self._client.get("/healthz")
            except httpx.HTTPError as exc:
                raise AsrRuntimeUnavailableError(
                    f"healthz unreachable: {exc}", retriable=True
                ) from exc
            if resp.status_code != 200:
                raise AsrRuntimeUnavailableError(
                    f"healthz returned {resp.status_code}", retriable=False
                )
            body = resp.json()
            status = body.get("status")
            if status == "ready":
                return
            if status == "error":
                raise AsrRuntimeUnavailableError(
                    f"runtime reports error: {body.get('last_error', 'unknown')}",
                    retriable=False,
                )
            if asyncio.get_event_loop().time() > deadline:
                raise AsrRuntimeUnavailableError(
                    f"warmup timeout — runtime stuck in {status!r}",
                    retriable=True,
                )
            if self._warmup_poll_interval_s > 0:
                await asyncio.sleep(self._warmup_poll_interval_s)

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk:
        payload = {
            "audio_bytes_b64": base64.standard_b64encode(audio_bytes).decode("ascii"),
            "sample_rate_hz": sample_rate_hz,
            "language_hint": language_hint,
        }
        try:
            resp = await self._client.post("/v1/transcribe/chunk", json=payload)
        except httpx.HTTPError as exc:
            raise AsrRuntimeUnavailableError(
                f"transcribe POST failed: {exc}", retriable=True
            ) from exc
        if resp.status_code != 200:
            body: dict[str, object]
            try:
                body = resp.json()
            except Exception:
                body = {}
            raise AsrRuntimeUnavailableError(
                str(body.get("message", f"HTTP {resp.status_code}")),
                error_code=str(body.get("error_code", "asr.runtime_unavailable")),
                retriable=bool(body.get("retriable", False)),
            )
        body = resp.json()
        return TranscriptChunk(
            text=str(body.get("text", "")),
            started_at=datetime.fromisoformat(body["started_at"]),
            ended_at=datetime.fromisoformat(body["ended_at"]),
            asr_provider_used="qwen3",
            confidence=None,
        )

    async def aclose(self) -> None:
        """Release the underlying httpx connection pool."""
        await self._client.aclose()


__all__ = ["AsrRuntimeUnavailableError", "RemoteAsrRuntimeClient"]
