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
        user_id="u_list",
        kind="pdf",
        original_name="a1.pdf",
        file_path="/tmp/a1.pdf",
        bytes_=100,
    )
    a2 = await repo.create(
        meeting_id="m_list",
        user_id="u_list",
        kind="image",
        original_name="b.png",
        file_path="/tmp/b.png",
        bytes_=200,
    )
    a3 = await repo.create(
        meeting_id="m_list",
        user_id="u_list",
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
        user_id="u_ownr",
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
        user_id="u_del",
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
        user_id="u_o",
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
        user_id="u_dd",
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
        user_id="u_g",
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
        user_id="u_a",
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
        user_id="u_sd",
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
        user_id="u_c",
        kind="pdf",
        original_name="new.pdf",
        file_path="/tmp/new.pdf",
        bytes_=12345,
    )

    assert att.id.startswith("att_")
    assert att.meeting_id == "m_c"
    assert att.user_id == "u_c"
    assert att.kind == "pdf"
    assert att.original_name == "new.pdf"
    assert att.bytes == 12345
    assert att.uploaded_at >= before
    assert att.deleted_at is None


# ─── Slice-24: staged (orphan) row support ───────────────────────────


async def _seed_user(session: AsyncSession, *, user_id: str) -> None:
    """Insert a user row without a meeting — for staging tests."""
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
    await session.commit()


@pytest.mark.asyncio
async def test_create_with_null_meeting_id_persists_staged(
    db_session: AsyncSession,
) -> None:
    """Slice-24: repository.create accepts meeting_id=None for staged rows."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user(db_session, user_id="u_stage")
    repo = AttachmentRepository(db_session)

    att = await repo.create(
        meeting_id=None,
        user_id="u_stage",
        kind="pdf",
        original_name="staged.pdf",
        file_path="/tmp/_staging/u_stage/att.pdf",
        bytes_=500,
    )

    assert att.meeting_id is None
    assert att.user_id == "u_stage"
    assert att.deleted_at is None


@pytest.mark.asyncio
async def test_list_staged_for_user_excludes_attached_and_other_user(
    db_session: AsyncSession,
) -> None:
    """list_staged_for_user only returns rows where:
    - user_id matches
    - meeting_id IS NULL
    - deleted_at IS NULL
    """
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_a", meeting_id="m_a")
    await _seed_user(db_session, user_id="u_b")
    repo = AttachmentRepository(db_session)

    staged_a = await repo.create(
        meeting_id=None,
        user_id="u_a",
        kind="pdf",
        original_name="staged_a.pdf",
        file_path="/tmp/staged_a.pdf",
        bytes_=100,
    )
    # Attached row for u_a — must NOT appear in staged list.
    await repo.create(
        meeting_id="m_a",
        user_id="u_a",
        kind="pdf",
        original_name="attached.pdf",
        file_path="/tmp/attached.pdf",
        bytes_=100,
    )
    # Staged row for u_b — must NOT appear in u_a's staged list.
    await repo.create(
        meeting_id=None,
        user_id="u_b",
        kind="pdf",
        original_name="other_user.pdf",
        file_path="/tmp/other.pdf",
        bytes_=100,
    )
    # Soft-deleted staged row for u_a — must NOT appear.
    sdel = await repo.create(
        meeting_id=None,
        user_id="u_a",
        kind="pdf",
        original_name="sdel.pdf",
        file_path="/tmp/sdel.pdf",
        bytes_=100,
    )
    await repo.delete_staged(attachment_id=sdel.id, user_id="u_a")

    rows = await repo.list_staged_for_user(user_id="u_a")
    ids = [r.id for r in rows]
    assert ids == [staged_a.id], f"expected only the active staged row for u_a; got {ids}"


@pytest.mark.asyncio
async def test_delete_staged_returns_none_for_attached_row(
    db_session: AsyncSession,
) -> None:
    """delete_staged refuses to act on an attached row (meeting_id IS NOT NULL)."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user_and_meeting(db_session, user_id="u_ds", meeting_id="m_ds")
    repo = AttachmentRepository(db_session)
    attached = await repo.create(
        meeting_id="m_ds",
        user_id="u_ds",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )

    result = await repo.delete_staged(attachment_id=attached.id, user_id="u_ds")
    assert result is None, "delete_staged MUST refuse attached rows"

    # Row is still present + still attached.
    rows = await repo.list_for_meeting(meeting_id="m_ds", user_id="u_ds")
    assert len(rows) == 1
    assert rows[0].deleted_at is None


@pytest.mark.asyncio
async def test_delete_staged_returns_none_for_other_user_row(
    db_session: AsyncSession,
) -> None:
    """delete_staged returns None when the staged row belongs to a different user."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user(db_session, user_id="u_owner")
    await _seed_user(db_session, user_id="u_stranger")
    repo = AttachmentRepository(db_session)
    staged = await repo.create(
        meeting_id=None,
        user_id="u_owner",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )

    result = await repo.delete_staged(attachment_id=staged.id, user_id="u_stranger")
    assert result is None


@pytest.mark.asyncio
async def test_delete_staged_soft_deletes_owner_row(
    db_session: AsyncSession,
) -> None:
    """delete_staged sets deleted_at on the owner's staged row + returns it."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user(db_session, user_id="u_owner2")
    repo = AttachmentRepository(db_session)
    staged = await repo.create(
        meeting_id=None,
        user_id="u_owner2",
        kind="pdf",
        original_name="x.pdf",
        file_path="/tmp/x.pdf",
        bytes_=100,
    )

    deleted = await repo.delete_staged(attachment_id=staged.id, user_id="u_owner2")
    assert deleted is not None
    assert deleted.deleted_at is not None

    # Second call returns None (already soft-deleted).
    again = await repo.delete_staged(attachment_id=staged.id, user_id="u_owner2")
    assert again is None


@pytest.mark.asyncio
async def test_count_staged_returns_sum_for_active_only(
    db_session: AsyncSession,
) -> None:
    """count_staged_for_user returns (file_count, total_bytes) for active staged rows only."""
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user(db_session, user_id="u_quota")
    await _seed_user_and_meeting(db_session, user_id="u_quota2", meeting_id="m_q2")
    repo = AttachmentRepository(db_session)

    await repo.create(
        meeting_id=None,
        user_id="u_quota",
        kind="pdf",
        original_name="a.pdf",
        file_path="/tmp/a.pdf",
        bytes_=1000,
    )
    await repo.create(
        meeting_id=None,
        user_id="u_quota",
        kind="pdf",
        original_name="b.pdf",
        file_path="/tmp/b.pdf",
        bytes_=2500,
    )
    # Attached row — must NOT count.
    await repo.create(
        meeting_id="m_q2",
        user_id="u_quota2",
        kind="pdf",
        original_name="attached.pdf",
        file_path="/tmp/at.pdf",
        bytes_=9999,
    )
    # Soft-deleted staged row — must NOT count.
    sdel = await repo.create(
        meeting_id=None,
        user_id="u_quota",
        kind="pdf",
        original_name="sdel.pdf",
        file_path="/tmp/sdel.pdf",
        bytes_=5000,
    )
    await repo.delete_staged(attachment_id=sdel.id, user_id="u_quota")

    count, total = await repo.count_staged_for_user(user_id="u_quota")
    assert count == 2
    assert total == 3500


@pytest.mark.asyncio
async def test_count_staged_zero_when_user_has_nothing(
    db_session: AsyncSession,
) -> None:
    from meeting_playbook.attachments.repository import AttachmentRepository

    await _seed_user(db_session, user_id="u_empty")
    repo = AttachmentRepository(db_session)

    count, total = await repo.count_staged_for_user(user_id="u_empty")
    assert count == 0
    assert total == 0
