"""End-to-end summary regeneration with attachments — slice-20c task 7.2.

Verifies the summarizer pipeline:
  1. Seed a meeting + 2 attachments (PNG + markdown)
  2. Build VertexProSummarizer with a mock client that records `contents`
  3. Confirm `contents` is a list[Part] when attachments exist
  4. Persist via SummaryRepository with the snapshot hash
  5. Confirm `get_with_stale_flag(current_attachment_snapshot_hash=...)`
     returns:
       - stale=False right after the upsert
       - stale=True after the attachment set changes
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from meeting_playbook.attachments.multimodal_context import (
    EMPTY_SET_SNAPSHOT_HASH,
    compute_attachment_snapshot_hash,
)
from meeting_playbook.attachments.repository import AttachmentRepository
from meeting_playbook.summarization.repository import SummaryRepository
from meeting_playbook.summarization.vertex_summarizer import VertexProSummarizer

_PNG_HEAD = bytes.fromhex("89504E470D0A1A0A")
_VALID_MD = "## 重點討論\n- a\n## 決議\n(無)\n## Action items\n- [TBD] x\n## 待解決問題\n(無)\n"


async def _seed_meeting(session, *, uid: str, mid: str) -> None:
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
            VALUES (:mid, :uid, 'Multi summary', '林經理', 'Sean')
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


def _capture_client(text_to_return: str):
    captured: list[object] = []
    client = MagicMock()

    async def _generate_content(**kw):
        captured.append(kw.get("contents"))
        return SimpleNamespace(text=text_to_return)

    client.aio.models.generate_content = _generate_content
    return client, captured


@pytest.mark.asyncio
async def test_summary_with_attachments_routes_parts_and_persists_snapshot(
    db_session, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Summarizer routes Parts list to LLM; runtime persists snapshot."""
    await _seed_meeting(db_session, uid="u_sm_mm", mid="m_sm_mm")

    png = tmp_path / "diagram.png"
    png.write_bytes(_PNG_HEAD + b"\x00" * 256)
    note = tmp_path / "agenda.md"
    note.write_text("# Agenda\n- topic A\n- topic B")
    await _seed_attachment(
        db_session,
        aid="att_sm_img",
        mid="m_sm_mm",
        file_path=str(png),
        kind="image",
        name="diagram.png",
    )
    await _seed_attachment(
        db_session,
        aid="att_sm_md",
        mid="m_sm_mm",
        file_path=str(note),
        kind="markdown",
        name="agenda.md",
    )

    client, captured = _capture_client(_VALID_MD)
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = VertexProSummarizer(
        client_factory=lambda: client,
        model_id="gemini-2.5-pro",
        session_factory=Session,
        locale="zh-TW",
    )

    markdown = await summarizer.summarize("m_sm_mm")
    assert markdown == _VALID_MD
    assert captured, "generate_content was never invoked"
    parts = captured[0]
    assert isinstance(parts, list), f"expected list[Part], got {type(parts).__name__}"
    assert len(parts) >= 2

    # Compute + persist the snapshot the same way the runtime would.
    async with Session() as s:
        attachments = await AttachmentRepository(s).list_for_meeting_internal(
            meeting_id="m_sm_mm",
        )
    snapshot = compute_attachment_snapshot_hash(list(attachments))
    assert snapshot != EMPTY_SET_SNAPSHOT_HASH

    async with Session() as s:
        await SummaryRepository(s).upsert(
            meeting_id="m_sm_mm",
            markdown=markdown,
            attachment_hash_snapshot=snapshot,
        )

    async with Session() as s:
        result = await SummaryRepository(s).get_with_stale_flag(
            "m_sm_mm",
            current_attachment_snapshot_hash=snapshot,
        )
    assert result is not None
    assert result.markdown == markdown
    assert result.is_stale is False

    # Adding a third attachment flips the stale flag.
    extra = tmp_path / "extra.md"
    extra.write_text("# Extra")
    await _seed_attachment(
        db_session,
        aid="att_sm_extra",
        mid="m_sm_mm",
        file_path=str(extra),
        kind="markdown",
        name="extra.md",
    )
    async with Session() as s:
        attachments_v2 = await AttachmentRepository(s).list_for_meeting_internal(
            meeting_id="m_sm_mm",
        )
    snapshot_v2 = compute_attachment_snapshot_hash(list(attachments_v2))
    assert snapshot_v2 != snapshot

    async with Session() as s:
        result_v2 = await SummaryRepository(s).get_with_stale_flag(
            "m_sm_mm",
            current_attachment_snapshot_hash=snapshot_v2,
        )
    assert result_v2 is not None
    assert result_v2.is_stale is True
