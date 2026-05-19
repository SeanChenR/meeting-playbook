"""Tus 1.0 protocol handler tests — slice-14 tasks 2.1 ~ 2.4.

Covers the four HTTP verbs that make up the tus 1.0 core + creation +
termination extensions:

- OPTIONS  : capability discovery (task 2.1)
- POST     : upload-session creation + 4 rejection paths (task 2.2)
- HEAD     : offset inspection (task 2.3)
- PATCH    : chunk append + offset advance + completion trigger (task 2.4)
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _encode_metadata(pairs: dict[str, str]) -> str:
    """Encode metadata per tus 1.0 spec: comma-separated `key value` pairs
    where value is base64(utf-8 bytes)."""
    parts = []
    for key, value in pairs.items():
        b64 = base64.b64encode(value.encode("utf-8")).decode("ascii")
        parts.append(f"{key} {b64}")
    return ",".join(parts)


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_eligible_meeting(
    db_url: str,
    *,
    user_id: str = "u_off",
    meeting_id: str = "m_off",
    minutes_past_end: int = 60,
) -> None:
    """Seed a meeting eligible for offline ingest: status=scheduled, end
    in the past, no recordings.
    """
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    base = datetime.now(UTC)
    started_at = base - timedelta(minutes=minutes_past_end + 30)
    ended_at = base - timedelta(minutes=minutes_past_end)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name,
                    status, scheduled_start_at, scheduled_end_at
                )
                VALUES (:mid, :uid, 'offline test', 'Counterparty', 'Me',
                        'scheduled', :start, :end)
                """
            ),
            {"mid": meeting_id, "uid": user_id, "start": started_at, "end": ended_at},
        )
    await engine.dispose()


def _build_client(db_url_sync: str, tmp_upload_dir: Path) -> TestClient:
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    import os

    os.environ["OFFLINE_UPLOAD_DIR"] = str(tmp_upload_dir)

    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


def _post_creation_headers(
    *,
    upload_length: int = 5_242_880,
    filename: str = "sample.mp3",
    mimetype: str = "audio/mpeg",
    actual_started_at: str | None = None,
) -> dict[str, str]:
    """Build the headers a tus-js-client would send on POST creation."""
    if actual_started_at is None:
        actual_started_at = (datetime.now(UTC) - timedelta(minutes=90)).isoformat()
    metadata = _encode_metadata(
        {
            "filename": filename,
            "mimetype": mimetype,
            "actual_started_at": actual_started_at,
        }
    )
    return {
        "X-User-Id": "u_off",
        "Tus-Resumable": "1.0.0",
        "Upload-Length": str(upload_length),
        "Upload-Metadata": metadata,
    }


# ─── OPTIONS (task 2.1) ────────────────────────────────────────────────


def test_options_advertises_tus_capabilities(_migrated_db_url, tmp_path):
    """Per spec `POST ... speaks tus 1.0 creation protocol` (OPTIONS clause):
    OPTIONS SHALL advertise four headers (`Tus-Resumable`, `Tus-Version`,
    `Tus-Max-Size`, `Tus-Extension`) so the tus-js-client discovers our
    capabilities before opening an upload session.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.options(
        "/api/meetings/m_off/recordings/offline_upload",
        headers={"X-User-Id": "u_off"},
    )

    assert response.status_code == 204, response.text
    assert response.headers.get("Tus-Resumable") == "1.0.0"
    assert response.headers.get("Tus-Version") == "1.0.0"
    assert response.headers.get("Tus-Max-Size") == "524288000"
    assert response.headers.get("Tus-Extension") == "creation,termination"


# ─── POST creation (task 2.2) ──────────────────────────────────────────


def test_post_creation_returns_201_with_location(_migrated_db_url, tmp_path):
    """Per spec scenario `Valid creation returns 201 with upload Location`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(),
    )

    assert response.status_code == 201, response.text
    assert response.headers.get("Tus-Resumable") == "1.0.0"
    location = response.headers.get("Location", "")
    assert location.startswith("/api/meetings/m_off/recordings/offline_upload/"), (
        f"Location must point at the upload session; got {location!r}"
    )
    # The upload id portion must be url-safe and non-trivial.
    upload_id = location.rsplit("/", 1)[-1]
    assert len(upload_id) >= 16, f"upload_id should be cryptographically random; got {upload_id!r}"


def test_post_creation_rejects_oversized_upload_length(_migrated_db_url, tmp_path):
    """Per spec scenario `Upload-Length over the max returns 413`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(upload_length=800_000_000),
    )

    assert response.status_code == 413, response.text
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.too_large", body


def test_post_creation_rejects_unsupported_mimetype(_migrated_db_url, tmp_path):
    """Per spec scenario `Unsupported mimetype returns 422`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(mimetype="video/mp4", filename="movie.mp4"),
    )

    assert response.status_code == 422, response.text
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.unsupported_format", body


def test_post_creation_rejects_future_actual_started_at(_migrated_db_url, tmp_path):
    """`actual_started_at` in the future must produce
    `offline_ingest.invalid_started_at` per the requirement body."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    future_iso = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(actual_started_at=future_iso),
    )

    assert response.status_code == 422, response.text
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.invalid_started_at", body


def test_post_creation_rejects_when_banner_conditions_not_met(_migrated_db_url, tmp_path):
    """Per spec scenario `Banner conditions no longer met returns 409` —
    meeting status flipped to in_progress between dialog open and submit.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    # Mutate the meeting to in_progress so the banner condition no longer holds.
    async def _flip_status():
        engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE meeting SET status = 'in_progress' WHERE id = 'm_off'"))
        await engine.dispose()

    asyncio.run(_flip_status())

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(),
    )

    assert response.status_code == 409, response.text
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.conditions_not_met", body


# ─── HEAD (task 2.3) ───────────────────────────────────────────────────


def _create_session_via_post(
    client: TestClient,
    *,
    upload_length: int = 5_242_880,
) -> str:
    """Create a tus session through the public POST endpoint and return
    its `upload_id`. Tests reuse this so HEAD / PATCH assertions exercise
    the same code path as production callers.
    """
    response = client.post(
        "/api/meetings/m_off/recordings/offline_upload",
        headers=_post_creation_headers(upload_length=upload_length),
    )
    assert response.status_code == 201, response.text
    location = response.headers["Location"]
    return location.rsplit("/", 1)[-1]


def test_head_returns_offset_zero_after_creation(_migrated_db_url, tmp_path):
    """Per spec scenario `HEAD before any PATCH returns offset zero`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1_048_576)

    response = client.head(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={"X-User-Id": "u_off", "Tus-Resumable": "1.0.0"},
    )

    assert response.status_code in (200, 204), response.status_code
    assert response.headers.get("Tus-Resumable") == "1.0.0"
    assert response.headers.get("Upload-Offset") == "0"
    assert response.headers.get("Upload-Length") == "1048576"
    # HEAD MUST NOT cache (per tus spec): the offset is volatile.
    cache_control = response.headers.get("Cache-Control", "")
    assert "no-store" in cache_control.lower(), (
        f"HEAD response should advertise Cache-Control: no-store; got {cache_control!r}"
    )


def test_head_returns_404_for_unknown_upload_id(_migrated_db_url, tmp_path):
    """Unknown session ids MUST yield 404 — no upload state should be
    inferable from headers on a missing session.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.head(
        "/api/meetings/m_off/recordings/offline_upload/no_such_session",
        headers={"X-User-Id": "u_off", "Tus-Resumable": "1.0.0"},
    )

    assert response.status_code == 404, response.status_code
    # HEAD bodies are empty, but `Tus-Resumable` SHOULD still be present.
    assert response.headers.get("Tus-Resumable") == "1.0.0"


# ─── PATCH (task 2.4) ──────────────────────────────────────────────────


def _patch_chunk(
    client: TestClient,
    *,
    upload_id: str,
    offset: int,
    body: bytes,
) -> object:
    """Helper: issue a tus PATCH with the canonical headers + body."""
    return client.patch(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(offset),
            "Content-Type": "application/offset+octet-stream",
        },
        content=body,
    )


def test_patch_appends_bytes_and_advances_offset(_migrated_db_url, tmp_path):
    """Per spec scenario `PATCH appends bytes and advances offset`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1_048_576)

    half = b"\xaa" * 524_288  # half of 1 MiB
    response = _patch_chunk(client, upload_id=upload_id, offset=0, body=half)

    assert response.status_code == 204, response.status_code
    assert response.headers.get("Upload-Offset") == "524288"
    assert response.headers.get("Tus-Resumable") == "1.0.0"

    staging = tmp_path / f"{upload_id}.partial"
    assert staging.exists()
    assert staging.stat().st_size == 524_288


def test_patch_rejects_mismatched_offset_without_truncating(_migrated_db_url, tmp_path):
    """Per spec scenario `Mismatched offset rejected for resume safety`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1_048_576)

    # Advance offset to 524288 with a valid PATCH first.
    initial = b"\xbb" * 524_288
    response = _patch_chunk(client, upload_id=upload_id, offset=0, body=initial)
    assert response.status_code == 204
    staging = tmp_path / f"{upload_id}.partial"
    assert staging.stat().st_size == 524_288

    # Now PATCH with the WRONG offset — server is at 524288 but client claims 0.
    bad_response = _patch_chunk(client, upload_id=upload_id, offset=0, body=b"\xcc" * 100)

    assert bad_response.status_code == 409, bad_response.status_code
    # Staging file MUST NOT be truncated on offset mismatch.
    assert staging.stat().st_size == 524_288


def test_patch_completion_triggers_pipeline_hook(_migrated_db_url, tmp_path, monkeypatch):
    """Per spec scenario `Completing PATCH triggers downstream pipeline`.

    Substitutes a stub `set_completion_handler` so the test asserts the
    handler is invoked exactly once when offset reaches upload_length.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    from meeting_playbook.offline_ingest import tus_protocol as tus

    calls: list[str] = []

    async def _stub(session):
        calls.append(session.upload_id)

    monkeypatch.setattr(tus, "_completion_handler", _stub)

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=4)

    response = _patch_chunk(client, upload_id=upload_id, offset=0, body=b"ABCD")
    assert response.status_code == 204
    assert response.headers.get("Upload-Offset") == "4"
    assert calls == [upload_id], (
        f"completion handler MUST be invoked exactly once with the session; got calls={calls}"
    )


def test_patch_returns_404_when_session_unknown(_migrated_db_url, tmp_path):
    """PATCH against an unknown upload_id MUST return 404 + `Tus-Resumable`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.patch(
        "/api/meetings/m_off/recordings/offline_upload/no_such_session",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"AAAA",
    )
    assert response.status_code == 404, response.status_code
    assert response.headers.get("Tus-Resumable") == "1.0.0"


def test_patch_rejects_missing_upload_offset_header(_migrated_db_url, tmp_path):
    """Missing `Upload-Offset` SHALL surface as 400 + the project error envelope."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1024)

    response = client.patch(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"AA",
    )
    assert response.status_code == 400, response.status_code
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.missing_upload_offset", body


def test_patch_rejects_wrong_content_type(_migrated_db_url, tmp_path):
    """Wrong `Content-Type` SHALL surface as 415 — tus 1.0 mandates
    `application/offset+octet-stream` on PATCH.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1024)

    response = client.patch(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/json",
        },
        content=b"{}",
    )
    assert response.status_code == 415, response.status_code
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.unsupported_content_type", body


def test_patch_rejects_empty_body(_migrated_db_url, tmp_path):
    """Empty PATCH body SHALL surface as 400 `offline_ingest.empty_patch`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=1024)

    response = client.patch(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"",
    )
    assert response.status_code == 400, response.status_code
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.empty_patch", body


def test_patch_rejects_overrun(_migrated_db_url, tmp_path):
    """PATCH whose append would exceed `Upload-Length` SHALL return 413
    `offline_ingest.too_large` and NOT append the offending bytes.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=4)

    response = client.patch(
        f"/api/meetings/m_off/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_off",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"AAAAA",  # 5 bytes, upload_length is 4
    )
    assert response.status_code == 413, response.status_code
    body = response.json()
    error_code = body.get("error_code") or body.get("detail", {}).get("error_code")
    assert error_code == "offline_ingest.too_large", body


def test_patch_swallows_completion_handler_exceptions(_migrated_db_url, tmp_path, monkeypatch):
    """If the pipeline completion handler raises, the upload itself MUST
    still report 204 — failure surfaces through the progress endpoint, not
    the PATCH response.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url)))

    from meeting_playbook.offline_ingest import tus_protocol as tus

    async def _exploding_handler(session):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(tus, "_completion_handler", _exploding_handler)

    client = _build_client(_migrated_db_url, tmp_path)
    upload_id = _create_session_via_post(client, upload_length=4)

    response = _patch_chunk(client, upload_id=upload_id, offset=0, body=b"DONE")
    assert response.status_code == 204
    assert response.headers.get("Upload-Offset") == "4"
