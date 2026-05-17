"""HTTP endpoint tests for meeting-attachment router — slice-20a tasks 3.1 + 3.2 + 3.3.

Covers every row of the per-file-type behaviour table (image / pdf / docx /
text / markdown) plus the auth + quota guards:

  - image (PNG 200KB) happy + BMP reject
  - PDF 1MB happy + zip-renamed-as-.pdf accepted (S20a doesn't sniff)
  - docx 500KB happy + 35MB reject quota_exceeded
  - txt 5KB happy
  - md 12KB happy
  - list owner 200 / non-owner 404
  - too_many: 6th attachment 422
  - delete 204 → list excludes + second DELETE 404
  - download 200 + Content-Disposition + 410 when file is gone
  - missing X-User-Id → 401 auth.gateway_bypass
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


def _png_bytes(size: int) -> bytes:
    """Minimal PNG header + filler so the total is `size` bytes."""
    # PNG magic header (8 bytes); rest is padding (the router only checks
    # content-type, not magic bytes).
    head = bytes.fromhex("89504E470D0A1A0A")
    return head + b"\x00" * (size - len(head))


def _pdf_bytes(size: int) -> bytes:
    head = b"%PDF-1.4\n"
    return head + b"\x00" * (size - len(head))


def _build_payload(size: int) -> bytes:
    """Generic filler bytes — exactly `size` bytes of zeros."""
    return b"\x00" * size


async def _seed_user_meeting(db_url_async: str, *, user_id: str, meeting_id: str) -> None:
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
    # Required settings — the Settings() singleton refuses to instantiate
    # without them, and create_app() triggers it via the lifespan loader.
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


# ─── Happy paths per kind ──────────────────────────────────────────────


def test_upload_png_200kb_returns_200_and_persists_file(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_a"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _png_bytes(200 * 1024)
    resp = client.post(
        "/api/meetings/m_a/attachments",
        headers={"X-User-Id": "u_a"},
        files={"file": ("screenshot.png", body, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["kind"] == "image"
    assert payload["original_name"] == "screenshot.png"
    assert payload["bytes"] == 200 * 1024

    # File on disk under {ATTACHMENT_DIR}/{meeting_id}/{att_id}.png
    meeting_dir = tmp_path / "m_a"
    files = list(meeting_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".png"
    assert files[0].read_bytes() == body


def test_upload_pdf_1mb_returns_200(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_p", meeting_id="m_p"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _pdf_bytes(1 * 1024 * 1024)
    resp = client.post(
        "/api/meetings/m_p/attachments",
        headers={"X-User-Id": "u_p"},
        files={"file": ("quote.pdf", body, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "pdf"


def test_upload_zip_renamed_as_pdf_is_accepted_no_magic_byte_sniff(_migrated_db_url, tmp_path, monkeypatch):
    """S20a deliberately does NOT sniff magic bytes — if mime says PDF, it's PDF."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_z", meeting_id="m_z"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    # PKZIP magic header
    body = bytes.fromhex("504B0304") + b"\x00" * 1024
    resp = client.post(
        "/api/meetings/m_z/attachments",
        headers={"X-User-Id": "u_z"},
        files={"file": ("disguised.pdf", body, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text


def test_upload_docx_500kb_returns_200(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_d", meeting_id="m_d"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _build_payload(500 * 1024)
    resp = client.post(
        "/api/meetings/m_d/attachments",
        headers={"X-User-Id": "u_d"},
        files={
            "file": (
                "contract.docx",
                body,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "docx"


def test_upload_text_5kb_returns_200(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_t", meeting_id="m_t"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = b"hello world\n" * 500  # ~6kb
    resp = client.post(
        "/api/meetings/m_t/attachments",
        headers={"X-User-Id": "u_t"},
        files={"file": ("agenda.txt", body, "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "text"


def test_upload_markdown_12kb_returns_200(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_m", meeting_id="m_m"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = b"# Notes\n\n" + b"x" * (12 * 1024 - 10)
    resp = client.post(
        "/api/meetings/m_m/attachments",
        headers={"X-User-Id": "u_m"},
        files={"file": ("notes.md", body, "text/markdown")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "markdown"


# ─── Rejection paths ──────────────────────────────────────────────────


def test_upload_bmp_is_rejected_unsupported_format(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_bp", meeting_id="m_bp"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = b"BM" + b"\x00" * 1024
    resp = client.post(
        "/api/meetings/m_bp/attachments",
        headers={"X-User-Id": "u_bp"},
        files={"file": ("legacy.bmp", body, "image/bmp")},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.unsupported_format"
    # No file should remain on disk
    meeting_dir = tmp_path / "m_bp"
    if meeting_dir.exists():
        assert list(meeting_dir.iterdir()) == []


def test_upload_35mb_docx_is_rejected_quota_exceeded(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_q", meeting_id="m_q"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _build_payload(35 * 1024 * 1024)
    resp = client.post(
        "/api/meetings/m_q/attachments",
        headers={"X-User-Id": "u_q"},
        files={
            "file": (
                "huge.docx",
                body,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.quota_exceeded"
    meeting_dir = tmp_path / "m_q"
    if meeting_dir.exists():
        assert list(meeting_dir.iterdir()) == []


def test_upload_sixth_file_is_rejected_too_many(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_6", meeting_id="m_6"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    for i in range(5):
        resp = client.post(
            "/api/meetings/m_6/attachments",
            headers={"X-User-Id": "u_6"},
            files={"file": (f"a{i}.txt", b"hi" * 100, "text/plain")},
        )
        assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/meetings/m_6/attachments",
        headers={"X-User-Id": "u_6"},
        files={"file": ("sixth.txt", b"hi" * 100, "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.too_many"


# ─── List endpoint ────────────────────────────────────────────────────


def test_list_returns_active_for_owner(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_l", meeting_id="m_l"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    client.post(
        "/api/meetings/m_l/attachments",
        headers={"X-User-Id": "u_l"},
        files={"file": ("a.txt", b"hello", "text/plain")},
    )

    resp = client.get("/api/meetings/m_l/attachments", headers={"X-User-Id": "u_l"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["original_name"] == "a.txt"


def test_list_non_owner_returns_404(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_ow", meeting_id="m_ow"))
    asyncio.run(
        _seed_user_meeting(_async_url(_migrated_db_url), user_id="u_other", meeting_id="m_other")
    )

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.get("/api/meetings/m_ow/attachments", headers={"X-User-Id": "u_other"})
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "meeting.not_found"


# ─── Delete + Download ────────────────────────────────────────────────


def test_delete_returns_204_and_subsequent_list_excludes(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_dl", meeting_id="m_dl"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    up = client.post(
        "/api/meetings/m_dl/attachments",
        headers={"X-User-Id": "u_dl"},
        files={"file": ("x.txt", b"goodbye", "text/plain")},
    )
    att_id = up.json()["id"]
    file_path = next((tmp_path / "m_dl").iterdir())

    delete = client.delete(
        f"/api/meetings/m_dl/attachments/{att_id}",
        headers={"X-User-Id": "u_dl"},
    )
    assert delete.status_code == 204
    # File removed from disk
    assert not file_path.exists()

    # Second DELETE → 404
    delete_again = client.delete(
        f"/api/meetings/m_dl/attachments/{att_id}",
        headers={"X-User-Id": "u_dl"},
    )
    assert delete_again.status_code == 404
    assert delete_again.json()["error_code"] == "attachment.not_found"

    # List no longer contains it
    listing = client.get("/api/meetings/m_dl/attachments", headers={"X-User-Id": "u_dl"})
    assert listing.json()["attachments"] == []


def test_download_returns_200_with_content_disposition(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_dn", meeting_id="m_dn"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    body = _pdf_bytes(2048)
    up = client.post(
        "/api/meetings/m_dn/attachments",
        headers={"X-User-Id": "u_dn"},
        files={"file": ("quote.pdf", body, "application/pdf")},
    )
    att_id = up.json()["id"]

    resp = client.get(
        f"/api/meetings/m_dn/attachments/{att_id}/download",
        headers={"X-User-Id": "u_dn"},
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert 'filename="quote.pdf"' in cd
    assert resp.content == body


def test_download_returns_410_when_file_missing(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user_meeting(_async_url(_migrated_db_url), user_id="u_xp", meeting_id="m_xp"))

    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    up = client.post(
        "/api/meetings/m_xp/attachments",
        headers={"X-User-Id": "u_xp"},
        files={"file": ("gone.txt", b"hi", "text/plain")},
    )
    att_id = up.json()["id"]
    # Simulate retention cleanup having unlinked the file
    next((tmp_path / "m_xp").iterdir()).unlink()

    resp = client.get(
        f"/api/meetings/m_xp/attachments/{att_id}/download",
        headers={"X-User-Id": "u_xp"},
    )
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "attachment.expired"


# ─── Auth gateway bypass ──────────────────────────────────────────────


def test_list_without_x_user_id_returns_401(_migrated_db_url, tmp_path, monkeypatch):
    client = _build_client(_migrated_db_url, tmp_path, monkeypatch)
    resp = client.get("/api/meetings/m_anything/attachments")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"
