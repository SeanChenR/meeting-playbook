"""VertexProSummarizer multimodal path tests — slice-20c task 5.1.

Verifies that the summarizer:
  - keeps the pre-slice contract when there are no attachments
    (contents=user_message string)
  - flips to a list-of-Parts payload when attachment rows exist for the
    meeting
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.summarization.vertex_summarizer import VertexProSummarizer

_VALID_MD = "## 重點討論\n- a\n## 決議\n(無)\n## Action items\n- [TBD] x\n## 待解決問題\n(無)\n"


async def _seed_meeting(db_session, *, mid: str) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_mm', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await db_session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_mm', 'Multi', 'C', 'Sean')
            """
        ),
        {"mid": mid},
    )
    await db_session.commit()


async def _seed_attachment(db_session, *, mid: str, file_path: str) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO meeting_attachment
              (id, meeting_id, file_path, kind, original_name, bytes, uploaded_at)
            VALUES
              (:aid, :mid, :path, 'markdown', 'agenda.md', 32, now())
            """
        ),
        {"aid": "att_mm", "mid": mid, "path": file_path},
    )
    await db_session.commit()


def _capture_client(text_to_return: str):
    """Mock client whose generate_content records the `contents` kwarg."""
    captured: list[object] = []
    client = MagicMock()

    async def _generate_content(**kw):
        captured.append(kw.get("contents"))
        return SimpleNamespace(text=text_to_return)

    client.aio.models.generate_content = _generate_content
    return client, captured


def _make_summarizer(migrated_engine, client) -> VertexProSummarizer:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    return VertexProSummarizer(
        client_factory=lambda: client,
        model_id="gemini-2.5-pro",
        session_factory=Session,
        locale="zh-TW",
    )


@pytest.mark.asyncio
async def test_no_attachments_passes_string_contents(db_session, migrated_engine):
    """Pre-slice contract: no attachments → contents is a string."""
    await _seed_meeting(db_session, mid="m_mm_empty")
    client, captured = _capture_client(_VALID_MD)
    summarizer = _make_summarizer(migrated_engine, client)

    out = await summarizer.summarize("m_mm_empty")
    assert out == _VALID_MD
    assert captured, "generate_content was never invoked"
    assert isinstance(captured[0], str), (
        f"contents must be a string, got {type(captured[0]).__name__}"
    )


@pytest.mark.asyncio
async def test_with_attachments_passes_parts_list_contents(
    db_session, migrated_engine, tmp_path: Path
):
    """Slice-20c: attachments present → contents is a list of Parts."""
    await _seed_meeting(db_session, mid="m_mm_full")
    note = tmp_path / "agenda.md"
    note.write_text("# agenda\n- topic A")
    await _seed_attachment(db_session, mid="m_mm_full", file_path=str(note))

    client, captured = _capture_client(_VALID_MD)
    summarizer = _make_summarizer(migrated_engine, client)

    out = await summarizer.summarize("m_mm_full")
    assert out == _VALID_MD
    assert captured, "generate_content was never invoked"
    contents = captured[0]
    assert isinstance(contents, list), (
        f"contents must be a Parts list when attachments exist, got {type(contents).__name__}"
    )
    assert len(contents) >= 1
