"""MeetingRepository tests — owner isolation + list ordering.

Per spec (slice-03-meeting-crud, meeting-management/spec.md):
- Requirement: Meeting belongs to exactly one user with strict ownership isolation
- Requirement: Meeting list is sorted newest-first by creation time
- Requirement: Meeting status defaults to scheduled at creation
- Requirement: Meeting carries an optional Calendar event reference
- Requirement: Meeting carries an ASR provider preference defaulting to whisper

The repository (`packages/backend/meeting_playbook/meetings/repository.py`)
is the single access path that all higher layers (router, future slices) MUST
use; tests pin its surface contract here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.repository import MeetingRepository


async def _seed_user(session: AsyncSession, *, user_id: str) -> None:
    """Insert a user row so the meeting FK is satisfied."""
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:id, :name, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": user_id, "name": user_id, "email": f"{user_id}@example.com"},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_list_by_user_returns_only_owners_meetings(db_session: AsyncSession):
    """Scenario: List returns only meetings owned by the requesting user."""
    await _seed_user(db_session, user_id="user_a")
    await _seed_user(db_session, user_id="user_b")

    repo = MeetingRepository(db_session)
    a1 = await repo.create(
        user_id="user_a",
        title="A's first",
        counterparty_display_name="林經理",
        me_display_name="Sean",
    )
    a2 = await repo.create(
        user_id="user_a",
        title="A's second",
        counterparty_display_name="王董",
        me_display_name="Sean",
    )
    await repo.create(
        user_id="user_b",
        title="B's only",
        counterparty_display_name="張總",
        me_display_name="Bob",
    )

    a_list = await repo.list_by_user("user_a")
    assert {m.id for m in a_list} == {a1.id, a2.id}, (
        "user A's list MUST NOT contain user B's meeting"
    )


@pytest.mark.asyncio
async def test_list_by_user_sorted_newest_first(db_session: AsyncSession):
    """Scenario: Multiple meetings sort newest first."""
    await _seed_user(db_session, user_id="user_sort")

    repo = MeetingRepository(db_session)
    m1 = await repo.create(
        user_id="user_sort",
        title="oldest",
        counterparty_display_name="C",
        me_display_name="Me",
    )
    m2 = await repo.create(
        user_id="user_sort",
        title="middle",
        counterparty_display_name="C",
        me_display_name="Me",
    )
    m3 = await repo.create(
        user_id="user_sort",
        title="newest",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    rows = await repo.list_by_user("user_sort")
    assert [m.id for m in rows] == [m3.id, m2.id, m1.id], (
        "list_by_user MUST return rows in DESC created_at order"
    )


@pytest.mark.asyncio
async def test_get_for_user_returns_none_when_owner_mismatches(db_session: AsyncSession):
    """Scenario: Reading another user's meeting returns 404 — repo layer signal is None."""
    await _seed_user(db_session, user_id="user_a")
    await _seed_user(db_session, user_id="user_b")

    repo = MeetingRepository(db_session)
    meeting_b = await repo.create(
        user_id="user_b",
        title="B's secret",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    assert await repo.get_for_user(user_id="user_a", meeting_id=meeting_b.id) is None
    assert await repo.get_for_user(user_id="user_b", meeting_id=meeting_b.id) is not None


@pytest.mark.asyncio
async def test_get_for_user_returns_none_when_meeting_missing(db_session: AsyncSession):
    """Missing rows look identical to owner-mismatch from the API surface."""
    await _seed_user(db_session, user_id="user_a")
    repo = MeetingRepository(db_session)
    assert await repo.get_for_user(user_id="user_a", meeting_id="m_does_not_exist") is None


@pytest.mark.asyncio
async def test_delete_for_user_refuses_other_users_meeting(db_session: AsyncSession):
    """Scenario: Deleting another user's meeting returns 404 — repo returns False and row stays."""
    await _seed_user(db_session, user_id="user_a")
    await _seed_user(db_session, user_id="user_b")

    repo = MeetingRepository(db_session)
    meeting_b = await repo.create(
        user_id="user_b",
        title="protected",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    deleted = await repo.delete_for_user(user_id="user_a", meeting_id=meeting_b.id)
    assert deleted is False, "user A MUST NOT be able to delete user B's meeting"

    # Owner can still delete their own.
    again = await repo.delete_for_user(user_id="user_b", meeting_id=meeting_b.id)
    assert again is True
    assert await repo.get_for_user(user_id="user_b", meeting_id=meeting_b.id) is None


@pytest.mark.asyncio
async def test_create_defaults_status_to_scheduled_and_calendar_event_id_to_none(
    db_session: AsyncSession,
):
    """Scenario: New meeting has status scheduled + Scenario: New meeting has null calendar_event_id."""
    await _seed_user(db_session, user_id="user_defaults")

    repo = MeetingRepository(db_session)
    meeting = await repo.create(
        user_id="user_defaults",
        title="defaults",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    assert meeting.status == "scheduled"
    assert meeting.calendar_event_id is None


@pytest.mark.asyncio
async def test_create_defaults_asr_provider_to_qwen3(db_session: AsyncSession):
    """Scenario: New meeting defaults to qwen3 (slice-11 migration 0008)."""
    await _seed_user(db_session, user_id="user_asr")

    repo = MeetingRepository(db_session)
    meeting = await repo.create(
        user_id="user_asr",
        title="asr default",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    assert meeting.asr_provider == "qwen3"


@pytest.mark.asyncio
async def test_create_with_scheduled_times(db_session: AsyncSession):
    """Slice-07: scheduled_start_at + scheduled_end_at round-trip via get_for_user."""
    from datetime import datetime

    await _seed_user(db_session, user_id="user_sched")
    start = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    end = datetime(2026, 6, 15, 15, 0, tzinfo=UTC)

    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_sched",
        title="with schedule",
        counterparty_display_name="林",
        me_display_name="Sean",
        scheduled_start_at=start,
        scheduled_end_at=end,
    )

    fetched = await repo.get_for_user(user_id="user_sched", meeting_id=created.id)
    assert fetched is not None
    assert fetched.scheduled_start_at == start
    assert fetched.scheduled_end_at == end


@pytest.mark.asyncio
async def test_create_without_scheduled_times_falls_back_to_now(db_session: AsyncSession):
    """Slice-15: scheduled_start_at became NOT NULL — when callers omit it,
    the repository back-fills with `now()` so the schema invariant holds;
    scheduled_end_at stays NULL because the column remained nullable.
    """
    await _seed_user(db_session, user_id="user_no_sched")

    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_no_sched",
        title="no schedule",
        counterparty_display_name="林",
        me_display_name="Sean",
    )

    assert created.scheduled_start_at is not None
    assert created.scheduled_end_at is None


@pytest.mark.asyncio
async def test_create_with_calendar_event_id(db_session: AsyncSession):
    """Slice-07: calendar_event_id is now a create() kwarg (was UPDATEd post-hoc)."""
    await _seed_user(db_session, user_id="user_cal")

    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_cal",
        title="from calendar",
        counterparty_display_name="林",
        me_display_name="Sean",
        calendar_event_id="gcal_evt_42",
    )

    assert created.calendar_event_id == "gcal_evt_42"


# ─── Slice-15: update_for_user ─────────────────────────────────────────


def _count_update_statements(engine, listener_ref):
    """Attach a SQLAlchemy `before_cursor_execute` listener that counts the
    UPDATE statements issued against the `meeting` table. Returns the
    counter list (mutable so the test reads it post-call).
    """
    from sqlalchemy import event

    statements: list[str] = []

    def _on_exec(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("UPDATE MEETING"):
            statements.append(statement)

    # SQLAlchemy async engines wrap a sync engine; attach to the sync core.
    sync_engine = getattr(engine, "sync_engine", engine)
    event.listen(sync_engine, "before_cursor_execute", _on_exec)
    listener_ref.append((sync_engine, _on_exec))
    return statements


def _detach_listener(listener_ref):
    from sqlalchemy import event

    for sync_engine, fn in listener_ref:
        event.remove(sync_engine, "before_cursor_execute", fn)
    listener_ref.clear()


@pytest.mark.asyncio
async def test_update_for_user_empty_fields_no_update(db_session: AsyncSession, migrated_engine):
    """Slice-15: empty `fields` dict → no UPDATE, returns current row.

    The repo should fall back to `get_for_user` and emit zero UPDATE
    statements against the `meeting` table.
    """
    await _seed_user(db_session, user_id="user_u4u_empty")
    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_u4u_empty",
        title="empty fields",
        counterparty_display_name="C",
        me_display_name="M",
        scheduled_start_at=datetime(2026, 6, 15, 14, tzinfo=UTC),
    )

    listener_ref: list = []
    statements = _count_update_statements(migrated_engine, listener_ref)
    try:
        result = await repo.update_for_user(
            user_id="user_u4u_empty", meeting_id=created.id, fields={}
        )
    finally:
        _detach_listener(listener_ref)

    assert result is not None
    assert result.id == created.id
    assert statements == [], f"empty fields MUST NOT emit any UPDATE; got {statements}"


@pytest.mark.asyncio
async def test_update_for_user_multi_field_single_update(db_session: AsyncSession, migrated_engine):
    """Slice-15: multiple fields MUST be written in exactly one UPDATE."""
    await _seed_user(db_session, user_id="user_u4u_multi")
    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_u4u_multi",
        title="before",
        counterparty_display_name="C",
        me_display_name="M",
        scheduled_start_at=datetime(2026, 6, 15, 14, tzinfo=UTC),
    )

    listener_ref: list = []
    statements = _count_update_statements(migrated_engine, listener_ref)
    try:
        result = await repo.update_for_user(
            user_id="user_u4u_multi",
            meeting_id=created.id,
            fields={
                "title": "after",
                "counterparty_display_name": "新對方",
                "scheduled_start_at": datetime(2026, 7, 1, 9, tzinfo=UTC),
            },
        )
    finally:
        _detach_listener(listener_ref)

    assert result is not None
    assert result.title == "after"
    assert result.counterparty_display_name == "新對方"
    assert len(statements) == 1, (
        f"multi-field UPDATE MUST be a single statement; got {len(statements)}"
    )


@pytest.mark.asyncio
async def test_update_for_user_cross_user_returns_none(db_session: AsyncSession):
    """Cross-user PATCH MUST return None and leave the row untouched."""
    await _seed_user(db_session, user_id="user_owner")
    await _seed_user(db_session, user_id="user_intruder")
    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_owner",
        title="owned",
        counterparty_display_name="C",
        me_display_name="M",
        scheduled_start_at=datetime(2026, 6, 15, 14, tzinfo=UTC),
    )

    result = await repo.update_for_user(
        user_id="user_intruder",
        meeting_id=created.id,
        fields={"title": "stolen"},
    )
    assert result is None

    # Row remains as-is.
    owner_view = await repo.get_for_user(user_id="user_owner", meeting_id=created.id)
    assert owner_view is not None
    assert owner_view.title == "owned"


@pytest.mark.asyncio
async def test_update_asr_provider_for_user_still_works_via_delegation(
    db_session: AsyncSession,
):
    """Slice-11 behaviour must not regress — `update_asr_provider_for_user`
    delegates to `update_for_user` per slice-15 design and still flips the
    column for the owner.
    """
    await _seed_user(db_session, user_id="user_asr")
    repo = MeetingRepository(db_session)
    created = await repo.create(
        user_id="user_asr",
        title="asr only",
        counterparty_display_name="C",
        me_display_name="M",
        scheduled_start_at=datetime(2026, 6, 15, 14, tzinfo=UTC),
    )

    result = await repo.update_asr_provider_for_user(
        user_id="user_asr", meeting_id=created.id, asr_provider="whisper"
    )
    assert result is not None
    assert result.asr_provider == "whisper"
