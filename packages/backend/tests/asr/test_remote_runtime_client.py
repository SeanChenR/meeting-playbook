"""RemoteAsrRuntimeClient tests (tasks 6.1 / 6.2).

These exercise the backend-side ASR provider that proxies to the
standalone asr-runtime micro-service. Network calls are mocked via
`httpx.MockTransport` so tests stay fast and CPU-only.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.remote_runtime_client import (
    AsrRuntimeUnavailableError,
    RemoteAsrRuntimeClient,
)


def _ok_chunk_handler() -> httpx.MockTransport:
    """Mock /v1/transcribe/chunk + /healthz endpoints with success responses."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path == "/v1/transcribe/chunk":
            now = datetime.now(UTC).isoformat()
            return httpx.Response(
                200,
                json={"text": "hello", "started_at": now, "ended_at": now},
            )
        return httpx.Response(404)

    return httpx.MockTransport(_handler)


def _failing_chunk_handler() -> httpx.MockTransport:
    """Mock /v1/transcribe/chunk to return the structured 503 envelope."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(
            503,
            json={
                "error_code": "asr.runtime_unavailable",
                "message": "stub: model crashed",
                "retriable": False,
            },
        )

    return httpx.MockTransport(_handler)


@pytest.mark.asyncio
async def test_implements_asr_provider_protocol() -> None:
    """isinstance(client, ASRProvider) → True (runtime_checkable check)."""
    client = RemoteAsrRuntimeClient(
        stream="me", runtime_url="http://127.0.0.1:8100", transport=_ok_chunk_handler()
    )
    assert isinstance(client, ASRProvider)
    assert client.name == "qwen3"


@pytest.mark.asyncio
async def test_transcribe_chunk_success_round_trip() -> None:
    """Successful POST returns a TranscriptChunk shaped per the base contract."""
    client = RemoteAsrRuntimeClient(
        stream="me", runtime_url="http://127.0.0.1:8100", transport=_ok_chunk_handler()
    )
    pcm = bytes(16000 * 2)
    chunk = await client.transcribe_chunk(pcm, sample_rate_hz=16000)
    assert chunk.text == "hello"
    assert chunk.asr_provider_used == "qwen3"
    assert chunk.started_at is not None
    assert chunk.ended_at is not None


@pytest.mark.asyncio
async def test_transcribe_chunk_503_raises_runtime_unavailable() -> None:
    """5xx → AsrRuntimeUnavailableError carrying the error_code."""
    client = RemoteAsrRuntimeClient(
        stream="me",
        runtime_url="http://127.0.0.1:8100",
        transport=_failing_chunk_handler(),
    )
    pcm = bytes(16000 * 2)
    with pytest.raises(AsrRuntimeUnavailableError) as exc_info:
        await client.transcribe_chunk(pcm, sample_rate_hz=16000)
    assert exc_info.value.error_code == "asr.runtime_unavailable"


@pytest.mark.asyncio
async def test_warmup_polls_healthz_until_ready() -> None:
    """warmup() returns once /healthz reports `ready`."""
    poll_count = {"value": 0}

    async def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            poll_count["value"] += 1
            # First two polls report loading, then ready.
            status = "ready" if poll_count["value"] >= 3 else "loading"
            return httpx.Response(200, json={"status": status})
        return httpx.Response(404)

    transport = httpx.MockTransport(_handler)
    client = RemoteAsrRuntimeClient(
        stream="me",
        runtime_url="http://127.0.0.1:8100",
        transport=transport,
        warmup_poll_interval_s=0.0,  # don't actually sleep in tests
    )
    await client.warmup()
    assert poll_count["value"] >= 3


@pytest.mark.asyncio
async def test_warmup_raises_on_status_error() -> None:
    """`/healthz` reporting `status: error` → AsrRuntimeUnavailableError."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "last_error": "boom"})

    client = RemoteAsrRuntimeClient(
        stream="me",
        runtime_url="http://127.0.0.1:8100",
        transport=httpx.MockTransport(_handler),
        warmup_poll_interval_s=0.0,
    )
    with pytest.raises(AsrRuntimeUnavailableError):
        await client.warmup()
