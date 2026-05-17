"""HTTP endpoint tests for the staging router — slice-24 task 3.1 + 3.2.

Covers spec meeting-attachment ADDED requirements:
- POST /api/attachments/staging → upload to user-scoped staging path
- GET  /api/attachments?status=pending → list user's staged rows
- DELETE /api/attachments/{id} → soft-delete staged row only
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
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


def _pdf_bytes(size: int) -> bytes:
    head = b"%PDF-1.4\n"
    return head + b"\x00" * (size - len(head))


async def _seed_user(db_url_async: str, *, user_id: str) -> None:
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO "user" (id, name, email, "emailVerified")
                    VALUES (:uid, :uid, :email, true)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"uid": user_id, "email": f"{user_id}@example.com"},
            )
            await s.commit()
    finally:
        await engine.dispose()


async def _seed_user_meeting(db_url_async: str, *, user_id: str, meeting_id: str) -> None:
    await _seed_user(db_url_async, user_id=user_id)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO meeting (
                        id, user_id, title, counterparty_display_name, me_display_name
                    )
                    VALUES (:mid, :uid, 'T', 'C', 'M')
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"mid": meeting_id, "uid": user_id},
            )
            await s.commit()
    finally:
        await engine.dispose()


async def _truncate(db_url_async: str) -> None:
    engine = create_async_engine(db_url_async, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text('TRUNCATE TABLE "meeting_attachment" RESTART IDENTITY CASCADE'))
            await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
            await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    finally:
        await engine.dispose()


def _build_client(
    db_url_sync: str, tmp_attachment_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """TestClient wired to test DB + tmp ATTACHMENT_DIR."""
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ATTACHMENT_DIR", str(tmp_attachment_dir))
    monkeypatch.setenv("DATABASE_URL", db_url_sync)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")

    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


async def _insert_staged(
    db_url_async: str,
    *,
    aid: str,
    user_id: str,
    file_path: str,
    age_seconds: int = 0,
    bytes_: int = 100,
) -> None:
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO meeting_attachment (
                        id, meeting_id, user_id, file_path, kind, original_name,
                        bytes, uploaded_at, deleted_at
                    )
                    VALUES (
                        :aid, NULL, :uid, :path, 'pdf', 'staged.pdf',
                        :bytes, now() - (:age || ' seconds')::interval, NULL
                    )
                    """
                ),
                {
                    "aid": aid,
                    "uid": user_id,
                    "path": file_path,
                    "bytes": bytes_,
                    "age": str(age_seconds),
                },
            )
            await s.commit()
    finally:
        await engine.dispose()


# ─── POST /api/attachments/staging ───────────────────────────────────


def test_upload_staged_pdf_returns_201_and_persists_file(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_up"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _pdf_bytes(2048)
    resp = client.post(
        "/api/attachments/staging",
        headers={"X-User-Id": "u_up"},
        files={"file": ("ok.pdf", body, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert payload["kind"] == "pdf"
    assert payload["original_name"] == "ok.pdf"
    assert payload["bytes"] == 2048

    # File on disk under ATTACHMENT_DIR/_staging/<user>/<id>.pdf
    staged_dir = tmp_path / "_staging" / "u_up"
    files = list(staged_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".pdf"
    assert files[0].read_bytes() == body


def test_upload_staged_unsupported_mime_returns_422(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_mime"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.post(
        "/api/attachments/staging",
        headers={"X-User-Id": "u_mime"},
        files={"file": ("weird.zip", b"PK\x03\x04junk", "application/zip")},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.unsupported_format"

    # Nothing written to disk.
    staged_dir = tmp_path / "_staging" / "u_mime"
    assert not staged_dir.exists() or not list(staged_dir.iterdir())


def test_upload_staged_eleventh_file_is_rejected_quota_exceeded(
    _migrated_db_url, tmp_path, monkeypatch
):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_qf"))
    # Pre-seed 10 staged rows.
    for i in range(10):
        asyncio.run(
            _insert_staged(
                _async_url(_migrated_db_url),
                aid=f"att_q_{i}",
                user_id="u_qf",
                file_path=str(tmp_path / "_staging" / "u_qf" / f"att_q_{i}.pdf"),
                bytes_=100,
            )
        )

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.post(
        "/api/attachments/staging",
        headers={"X-User-Id": "u_qf"},
        files={"file": ("eleventh.pdf", _pdf_bytes(100), "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.staging_quota_exceeded"


# ─── GET /api/attachments?status=pending ────────────────────────────


def test_list_staged_returns_only_active_owner_rows(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_la", meeting_id="m_la"))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_lb"))
    # 2 active staged for u_la (different upload ages)
    asyncio.run(
        _insert_staged(
            _async_url(_migrated_db_url),
            aid="att_la_1",
            user_id="u_la",
            file_path="/tmp/la_1.pdf",
            age_seconds=10,
        )
    )
    asyncio.run(
        _insert_staged(
            _async_url(_migrated_db_url),
            aid="att_la_2",
            user_id="u_la",
            file_path="/tmp/la_2.pdf",
            age_seconds=0,
        )
    )
    # An attached row for u_la — should NOT appear in staged list.
    engine = create_async_engine(_async_url(_migrated_db_url), future=True)
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async def _seed_attached():
            async with Session() as s:
                await s.execute(
                    text(
                        """
                        INSERT INTO meeting_attachment (
                            id, meeting_id, user_id, file_path, kind,
                            original_name, bytes, uploaded_at
                        )
                        VALUES (
                            'att_la_attached', 'm_la', 'u_la', '/tmp/la_att.pdf',
                            'pdf', 'x.pdf', 100, now()
                        )
                        """
                    )
                )
                await s.commit()

        asyncio.run(_seed_attached())
    finally:
        asyncio.run(engine.dispose())
    # Staged row for the other user.
    asyncio.run(
        _insert_staged(
            _async_url(_migrated_db_url),
            aid="att_lb_1",
            user_id="u_lb",
            file_path="/tmp/lb_1.pdf",
        )
    )

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.get(
        "/api/attachments?status=pending",
        headers={"X-User-Id": "u_la"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    ids = [a["id"] for a in payload["attachments"]]
    # Returned oldest-first (uploaded_at asc).
    assert ids == ["att_la_1", "att_la_2"], f"got {ids}"


def test_list_staged_invalid_status_returns_422(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_inv"))
    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.get(
        "/api/attachments?status=archived",
        headers={"X-User-Id": "u_inv"},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.invalid_status_filter"


def test_list_staged_missing_status_returns_422(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_inv2"))
    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.get("/api/attachments", headers={"X-User-Id": "u_inv2"})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.invalid_status_filter"


# ─── DELETE /api/attachments/{id} ─────────────────────────────────────


def test_delete_staged_returns_204_and_unlinks_file(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_del"))

    # Put a file on disk + a corresponding staged row.
    staged_dir = tmp_path / "_staging" / "u_del"
    staged_dir.mkdir(parents=True, exist_ok=True)
    on_disk = staged_dir / "att_del.pdf"
    on_disk.write_bytes(b"\x00" * 100)
    asyncio.run(
        _insert_staged(
            _async_url(_migrated_db_url),
            aid="att_del",
            user_id="u_del",
            file_path=str(on_disk),
        )
    )

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.delete(
        "/api/attachments/att_del",
        headers={"X-User-Id": "u_del"},
    )
    assert resp.status_code == 204, resp.text
    assert not on_disk.exists()


def test_delete_attached_row_returns_404(_migrated_db_url, tmp_path, monkeypatch):
    """Calling DELETE /api/attachments/<id> on an attached row returns 404."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_at", meeting_id="m_at"))

    # Insert an attached row.
    engine = create_async_engine(_async_url(_migrated_db_url), future=True)
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async def _seed():
            async with Session() as s:
                await s.execute(
                    text(
                        """
                        INSERT INTO meeting_attachment (
                            id, meeting_id, user_id, file_path, kind,
                            original_name, bytes, uploaded_at
                        )
                        VALUES (
                            'att_attached_404', 'm_at', 'u_at', '/tmp/x.pdf',
                            'pdf', 'x.pdf', 100, now()
                        )
                        """
                    )
                )
                await s.commit()

        asyncio.run(_seed())
    finally:
        asyncio.run(engine.dispose())

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.delete(
        "/api/attachments/att_attached_404",
        headers={"X-User-Id": "u_at"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "attachment.not_found"


def test_delete_cross_user_staged_returns_404(_migrated_db_url, tmp_path, monkeypatch):
    """A user can't delete another user's staged row — 404 with no info leak."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_x1"))
    asyncio.run(_seed_user(_async_url(_migrated_db_url), user_id="u_x2"))

    asyncio.run(
        _insert_staged(
            _async_url(_migrated_db_url),
            aid="att_xstage",
            user_id="u_x1",
            file_path="/tmp/x1.pdf",
        )
    )

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.delete(
        "/api/attachments/att_xstage",
        headers={"X-User-Id": "u_x2"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "attachment.not_found"
