"""End-to-end playbook regeneration with attachments — slice-20c task 7.1.

Verifies the full multimodal loop:
  1. Seed a meeting + 2 attachments (PNG + markdown — the latter substitutes
     for PDF because pypdf needs font-aware fixtures to round-trip text)
  2. Run PlaybookGenerator with a mock CallModel that records `contents`
  3. Confirm `contents` is a `list[Part]` (image part + combined text part)
  4. Upsert via PlaybookRepository with the attachment-set snapshot
  5. Confirm `get_with_stale_flag` returns:
       - stale=False right after the upsert
       - stale=True after the live attachment set changes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from meeting_playbook.attachments.multimodal_context import (
    EMPTY_SET_SNAPSHOT_HASH,
    compute_attachment_snapshot_hash,
)
from meeting_playbook.attachments.repository import AttachmentRepository
from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.playbook_generation.generator import (
    CONTENT_FIELDS,
    PlaybookGenerator,
)
from meeting_playbook.playbooks.repository import PlaybookRepository

_PNG_HEAD = bytes.fromhex("89504E470D0A1A0A")


def _full_draft_json() -> str:
    return json.dumps({field: f"value for {field}" * 3 for field in CONTENT_FIELDS})


async def _seed_user_meeting(session, *, uid: str, mid: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, 'Sean', :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": uid, "email": f"{uid}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, :uid, 'Multi briefing', '林經理', 'Sean')
            """
        ),
        {"mid": mid, "uid": uid},
    )
    await session.commit()


async def _seed_attachment(
    session, *, aid: str, mid: str, file_path: str, kind: str, name: str
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO meeting_attachment
              (id, meeting_id, file_path, kind, original_name, bytes, uploaded_at)
            VALUES
              (:aid, :mid, :path, :kind, :name, 128, now())
            """
        ),
        {"aid": aid, "mid": mid, "path": file_path, "kind": kind, "name": name},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_playbook_generation_with_attachments_persists_snapshot(
    db_session, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Generator routes Parts list to LLM; repository persists snapshot."""
    await _seed_user_meeting(db_session, uid="u_pb_mm", mid="m_pb_mm")

    # PNG + markdown attachments on disk + rows.
    png = tmp_path / "diagram.png"
    png.write_bytes(_PNG_HEAD + b"\x00" * 256)
    note = tmp_path / "agenda.md"
    note.write_text("# Agenda\n- topic A\n- topic B")
    await _seed_attachment(
        db_session,
        aid="att_img",
        mid="m_pb_mm",
        file_path=str(png),
        kind="image",
        name="diagram.png",
    )
    await _seed_attachment(
        db_session,
        aid="att_md",
        mid="m_pb_mm",
        file_path=str(note),
        kind="markdown",
        name="agenda.md",
    )

    received: list[object] = []

    async def _capture(contents: object) -> str:
        received.append(contents)
        return _full_draft_json()

    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with Session() as s:
        attachments = await AttachmentRepository(s).list_for_meeting_internal(
            meeting_id="m_pb_mm",
        )
    assert len(attachments) == 2

    event = CalendarEvent(
        id="evt_pb_mm",
        title="Multi briefing",
        start="2026-05-20T10:00:00+08:00",
        end="2026-05-20T11:00:00+08:00",
        attendees=["alex@example.com"],
        description="",
        organizer="me@example.com",
        organizer_email="me@example.com",
    )
    gen = PlaybookGenerator(call_model=_capture, timeout_seconds=5.0)
    draft = await gen.generate(
        event,
        viewer_email="me@example.com",
        viewer_name="Sean",
        attachment_refs=list(attachments),
    )

    # Mock saw a Parts list (multimodal path engaged).
    assert received, "call_model was never invoked"
    parts = received[0]
    assert isinstance(parts, list), f"expected list[Part], got {type(parts).__name__}"
    assert len(parts) >= 2  # image + combined text

    # Snapshot persists; subsequent stale check returns False.
    snapshot = compute_attachment_snapshot_hash(list(attachments))
    assert snapshot != EMPTY_SET_SNAPSHOT_HASH

    payload: dict[str, object] = {**draft, "attachment_hash_snapshot": snapshot}
    async with Session() as s:
        await PlaybookRepository(s).upsert_for_meeting(
            "m_pb_mm",
            payload,  # type: ignore[arg-type]
        )

    async with Session() as s:
        result = await PlaybookRepository(s).get_with_stale_flag(
            "m_pb_mm",
            current_attachment_snapshot_hash=snapshot,
        )
    assert result is not None
    assert result.is_stale is False

    # Add a third attachment → snapshot changes → stale flips to True.
    extra = tmp_path / "extra.md"
    extra.write_text("# Extra")
    await _seed_attachment(
        db_session,
        aid="att_extra",
        mid="m_pb_mm",
        file_path=str(extra),
        kind="markdown",
        name="extra.md",
    )
    async with Session() as s:
        attachments_v2 = await AttachmentRepository(s).list_for_meeting_internal(
            meeting_id="m_pb_mm",
        )
    snapshot_v2 = compute_attachment_snapshot_hash(list(attachments_v2))
    assert snapshot_v2 != snapshot

    async with Session() as s:
        result_v2 = await PlaybookRepository(s).get_with_stale_flag(
            "m_pb_mm",
            current_attachment_snapshot_hash=snapshot_v2,
        )
    assert result_v2 is not None
    assert result_v2.is_stale is True
