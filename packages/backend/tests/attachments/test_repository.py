"""AttachmentRepository tests — slice-20a task 2.2.

Verifies the methods in `meeting_playbook.attachments.repository`:

- `list_for_meeting(meeting_id, user_id)` returns only active rows for the
  owner. Non-owners get an empty list (404-shaped at the API layer).
- `create(...)` inserts a new row and returns it.
- `soft_delete(attachment_id, user_id)` flips `deleted_at` and returns the
  refreshed row (or None when the attachment doesn't exist / isn't owned).
- `get_for_download(attachment_id, user_id)` returns the active row when
  the user owns the parent meeting; None otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_user_and_meeting(session: AsyncSession, *, user_id: str, meeting_id: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, :uid, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": user_id, "email": f"{user_id}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, :uid, 'T', 'C', 'M')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"mid": meeting_id, "uid": user_id},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_list_for_meeting_returns_only_active_rows_for_owner(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_list", meeting_id="m_list")
    repo = AttachmentRepository(db_session)

    # 2 active + 1 soft-deleted
    a1 = await repo.create(
        meeting_id="m_list",
        kind="pdf",
        original_name="a1.pdf",
        file_path="/tmp/a1.pdf",
        bytes_=100,
    )
    a2 = await repo.create(
        meeting_id="m_list",
        kind="image",
        original_name="b.png",
        file_path="/tmp/b.png",
        bytes_=200,
    )
    a3 = await repo.create(
        meeting_id="m_list",
        kind="text",
        original_name="c.txt",
        file_path="/tmp/c.txt",
        bytes_=50,
    )
    await repo.soft_delete(attachment_id=a3.id, user_id="u_list")

    rows = await repo.list_for_meeting(meeting_id="m_list", user_id="u_list")
    ids = {r.id for r in rows}
    assert ids == {a1.id, a2.id}, f"expected only active rows; got {ids}"


@pytest.mark.asyncio
async def test_list_for_meeting_returns_empty_for_non_owner(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_ownr", meeting_id="m_ownr")
    await _seed_user_and_meeting(db_session, user_id="u_other", meeting_id="m_other")
    repo = AttachmentRepository(db_session)
    await repo.create(
        meeting_id="m_ownr",
        kind="pdf",
        original_name="a.pdf",
        file_path="/tmp/a.pdf",
        bytes_=100,
    )

    rows = await repo.list_for_meeting(meeting_id="m_ownr", user_id="u_other")
    assert rows == []


@pytest.mark.asyncio
async def test_soft_delete_sets_deleted_at_and_subsequent_list_excludes(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_del", meeting_id="m_del")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_del",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )

    deleted = await repo.soft_delete(attachment_id=att.id, user_id="u_del")
    assert deleted is not None
    assert deleted.deleted_at is not None

    rows = await repo.list_for_meeting(meeting_id="m_del", user_id="u_del")
    assert rows == []


@pytest.mark.asyncio
async def test_soft_delete_non_owner_returns_none(db_session: AsyncSession) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_o", meeting_id="m_o")
    await _seed_user_and_meeting(db_session, user_id="u_x", meeting_id="m_x")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_o",
        kind="pdf",
        original_name="z.pdf",
        file_path="/tmp/z.pdf",
        bytes_=100,
    )

    result = await repo.soft_delete(attachment_id=att.id, user_id="u_x")
    assert result is None


@pytest.mark.asyncio
async def test_soft_delete_already_deleted_returns_none(db_session: AsyncSession) -> None:
    """Double-DELETE on a row whose deleted_at is already set returns None."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_dd", meeting_id="m_dd")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_dd",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )
    first = await repo.soft_delete(attachment_id=att.id, user_id="u_dd")
    assert first is not None

    second = await repo.soft_delete(attachment_id=att.id, user_id="u_dd")
    assert second is None


@pytest.mark.asyncio
async def test_get_for_download_returns_active_for_owner(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_g", meeting_id="m_g")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_g",
        kind="pdf",
        original_name="d.pdf",
        file_path="/tmp/d.pdf",
        bytes_=100,
    )

    found = await repo.get_for_download(attachment_id=att.id, user_id="u_g")
    assert found is not None
    assert found.id == att.id


@pytest.mark.asyncio
async def test_get_for_download_returns_none_for_non_owner(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_a", meeting_id="m_a")
    await _seed_user_and_meeting(db_session, user_id="u_b", meeting_id="m_b")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_a",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )

    found = await repo.get_for_download(attachment_id=att.id, user_id="u_b")
    assert found is None


@pytest.mark.asyncio
async def test_get_for_download_returns_none_for_soft_deleted(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_sd", meeting_id="m_sd")
    repo = AttachmentRepository(db_session)
    att = await repo.create(
        meeting_id="m_sd",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )
    await repo.soft_delete(attachment_id=att.id, user_id="u_sd")

    found = await repo.get_for_download(attachment_id=att.id, user_id="u_sd")
    assert found is None


@pytest.mark.asyncio
async def test_create_persists_row_with_uploaded_at(db_session: AsyncSession) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_c", meeting_id="m_c")
    repo = AttachmentRepository(db_session)
    before = datetime.now(UTC) - timedelta(seconds=1)

    att = await repo.create(
        meeting_id="m_c",
        kind="pdf",
        original_name="new.pdf",
        file_path="/tmp/new.pdf",
        bytes_=12345,
    )

    assert att.id.startswith("att_")
    assert att.meeting_id == "m_c"
    assert att.kind == "pdf"
    assert att.original_name == "new.pdf"
    assert att.bytes == 12345
    assert att.uploaded_at >= before
    assert att.deleted_at is None
