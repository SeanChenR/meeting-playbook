"""Slice-20b: `POST /api/meetings` accepts `calendar_event_id` + `attachments[]`.

Per spec deltas:
- `meeting-management` ADDED requirement "POST /api/meetings accepts an
  attachments list that associates pre-uploaded attachments with the new
  meeting" — ownership + meeting_id IS NULL validation BEFORE meeting create.
- `meeting-management` MODIFIED requirement "Meeting carries an optional
  Calendar event reference" — calendar_event_id persists, triggers generator.
- `playbook-generation` ADDED requirement "Playbook generation is triggered
  by POST /api/meetings when calendar_event_id is supplied" — generator
  runs, playbook upserted; absent calendar_event_id = no generator call.

Test design note: the `attachment` table is owned by slice-20a (sibling
slice). To keep S20b tests self-contained, this file CREATEs the minimum
attachment table shape S20b needs (id / user_id / meeting_id) before each
test and DROPs it after. When S20a lands its migration, this fixture
becomes a no-op (the table already exists).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.calendar.dependencies import (
    get_calendar_client_dependency,
    get_playbook_generator_dependency,
)
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.playbook_generation.generator import (
    PlaybookGenerationFailed,
    PlaybookGenerationTimeout,
)
from meeting_playbook.server import create_app

_ATTACHMENT_DDL = """
CREATE TABLE IF NOT EXISTS attachment (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    meeting_id TEXT REFERENCES meeting(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


@pytest_asyncio.fixture
async def attachment_table(migrated_engine: AsyncEngine) -> AsyncIterator[None]:
    """Create the S20a attachment table shape for S20b tests.

    Once S20a's migration lands, this becomes a no-op (IF NOT EXISTS).
    On teardown the table is fully dropped so it does not block the
    session-wide alembic downgrade run by the next test session.
    """
    async with migrated_engine.begin() as conn:
        await conn.execute(text(_ATTACHMENT_DDL))
    yield
    async with migrated_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS attachment CASCADE"))


def _sample_event(event_id: str = "gcal_evt_42") -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title="Q3 review",
        start=datetime.now(UTC).isoformat(),
        end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        attendees=["Sean <sean@example.com>", "Lin <lin@acme.com>"],
        description="quarterly review",
        organizer="Sean",
        organizer_email="sean@example.com",
    )


class _StubCalendarClient:
    def __init__(self, *, get_event=None):
        self._get_event = get_event

    async def get_upcoming_events(self, _user_id: str, hours: int = 24):
        return []

    async def get_event(self, _user_id: str, event_id: str):
        if self._get_event is not None:
            return await self._get_event(event_id)
        return _sample_event(event_id)


class _StubPlaybookGenerator:
    def __init__(self, *, draft=None, error=None):
        self._draft = draft or {
            "free_form_markdown": "# Brief\n",
            "objective": "obj",
            "counterparty_profile": "cp",
            "anticipated_topics": "topics",
            "anticipated_objections": "objections",
            "talking_points": "tps",
            "red_lines": "rl",
        }
        self._error = error
        self.calls: list[dict] = []

    async def generate(self, event, *, viewer_email, viewer_name):
        self.calls.append(
            {"event": event, "viewer_email": viewer_email, "viewer_name": viewer_name}
        )
        if self._error is not None:
            raise self._error
        return self._draft


@pytest_asyncio.fixture
async def api_client_factory(migrated_engine: AsyncEngine):
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    def _make_client(*, calendar_client=None, playbook_generator=None):
        app = create_app()
        app.dependency_overrides[get_session_dependency] = _override_session
        app.dependency_overrides[get_calendar_client_dependency] = lambda: (
            calendar_client or _StubCalendarClient()
        )
        app.dependency_overrides[get_playbook_generator_dependency] = lambda: (
            playbook_generator or _StubPlaybookGenerator()
        )
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://gateway")

    return _make_client


async def _seed_user(engine: AsyncEngine, user_id: str) -> None:
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


async def _insert_attachment(
    engine: AsyncEngine,
    *,
    attachment_id: str,
    user_id: str,
    meeting_id: str | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO attachment (id, user_id, meeting_id)
                VALUES (:aid, :uid, :mid)
                """
            ),
            {"aid": attachment_id, "uid": user_id, "mid": meeting_id},
        )


# ─── Calendar event id triggers generator ───────────────────────────────────


@pytest.mark.asyncio
async def test_create_with_calendar_event_id_triggers_generator(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Create meeting with calendar_event_id triggers Playbook generation."""
    await _seed_user(migrated_engine, "u_alpha")
    gen = _StubPlaybookGenerator()
    cal = _StubCalendarClient()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings",
            headers={
                "X-User-Id": "u_alpha",
                "X-User-Email": "u_alpha@example.com",
                "X-User-Name": "Alpha",
            },
            json={
                "title": "Q3 review",
                "counterparty_display_name": "林經理",
                "me_display_name": "Sean",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "calendar_event_id": "gcal_evt_42",
                "attachments": [],
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["calendar_event_id"] == "gcal_evt_42"
    assert len(gen.calls) == 1, "Generator must be called when calendar_event_id is set"

    # Playbook persisted via PlaybookRepository.upsert_for_meeting.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT objective FROM playbook WHERE meeting_id = :mid"),
            {"mid": body["id"]},
        )
        row = rows.first()
        assert row is not None
        assert row.objective == "obj"


# ─── No calendar_event_id → no generator call ───────────────────────────────


@pytest.mark.asyncio
async def test_create_without_calendar_event_id_does_not_call_generator(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Create meeting without calendar_event_id does not invoke the generator."""
    await _seed_user(migrated_engine, "u_manual")
    gen = _StubPlaybookGenerator()
    async with api_client_factory(playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_manual"},
            json={
                "title": "manual",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
            },
        )
    assert resp.status_code == 201, resp.text
    assert len(gen.calls) == 0, "Generator MUST NOT be called when calendar_event_id is absent"
    body = resp.json()
    assert body["calendar_event_id"] is None


# ─── Attachments write back meeting_id ──────────────────────────────────────


@pytest.mark.asyncio
async def test_attachments_get_meeting_id_written_back(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Successful create attaches all supplied attachments to the new meeting."""
    await _seed_user(migrated_engine, "u_owner")
    await _insert_attachment(migrated_engine, attachment_id="att_1", user_id="u_owner")
    await _insert_attachment(migrated_engine, attachment_id="att_2", user_id="u_owner")

    async with api_client_factory() as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_owner"},
            json={
                "title": "with attachments",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "attachments": ["att_1", "att_2"],
            },
        )
    assert resp.status_code == 201, resp.text
    meeting_id = resp.json()["id"]

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id, meeting_id FROM attachment WHERE id IN ('att_1', 'att_2')")
        )
        records = {r.id: r.meeting_id for r in rows}
        assert records == {"att_1": meeting_id, "att_2": meeting_id}


# ─── Other user's attachment is rejected ────────────────────────────────────


@pytest.mark.asyncio
async def test_attachment_owned_by_other_user_is_rejected_with_attachment_not_attachable(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Attachment owned by another user is rejected with attachment.not_attachable."""
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    await _insert_attachment(migrated_engine, attachment_id="att_other", user_id="u_b")

    async with api_client_factory() as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_a"},
            json={
                "title": "X",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "attachments": ["att_other"],
            },
        )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.not_attachable"

    # No meeting was created.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_a"},
        )
        assert rows.first() is None
        # Attachment unchanged.
        att_rows = await conn.execute(
            text("SELECT user_id, meeting_id FROM attachment WHERE id = 'att_other'")
        )
        att = att_rows.first()
        assert att.user_id == "u_b"
        assert att.meeting_id is None


# ─── Already-attached attachment is rejected ────────────────────────────────


@pytest.mark.asyncio
async def test_already_attached_attachment_is_rejected(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Already-attached attachment is rejected with attachment.not_attachable."""
    await _seed_user(migrated_engine, "u_take")

    # Build an existing meeting and attach the file to it.
    async with api_client_factory() as c:
        prior = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_take"},
            json={
                "title": "prior",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
            },
        )
        prior_id = prior.json()["id"]
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_taken",
        user_id="u_take",
        meeting_id=prior_id,
    )

    async with api_client_factory() as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_take"},
            json={
                "title": "X",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "attachments": ["att_taken"],
            },
        )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "attachment.not_attachable"


# ─── Empty attachments list creates meeting normally ────────────────────────


@pytest.mark.asyncio
async def test_empty_attachments_list_creates_meeting_normally(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Empty or omitted attachments list creates a meeting with no attachments."""
    await _seed_user(migrated_engine, "u_empty")
    async with api_client_factory() as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_empty"},
            json={
                "title": "no attach",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "attachments": [],
            },
        )
    assert resp.status_code == 201
    assert resp.json()["calendar_event_id"] is None


# ─── Generator failure leaves meeting + attachments persisted ───────────────


@pytest.mark.asyncio
async def test_generator_timeout_persists_meeting_and_attachments(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Generator failure leaves the meeting and attachments persisted.

    The 504 envelope is `playbook.generation_timeout` — the meeting row and
    the attachment-row write-back already happened in the same transaction
    BEFORE the generator was invoked, so the user sees a meeting in their
    list with no Playbook (slice-04 auto-create empty draft NOT applied
    when calendar_event_id is set — generator owns the playbook).
    """
    await _seed_user(migrated_engine, "u_gen_fail")
    await _insert_attachment(migrated_engine, attachment_id="att_a", user_id="u_gen_fail")
    gen = _StubPlaybookGenerator(error=PlaybookGenerationTimeout("60s"))
    async with api_client_factory(playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_gen_fail"},
            json={
                "title": "Q3",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "calendar_event_id": "gcal_evt_42",
                "attachments": ["att_a"],
            },
        )
    assert resp.status_code == 504
    assert resp.json()["error_code"] == "playbook.generation_timeout"

    # Meeting + attachment still persist.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_gen_fail"},
        )
        meeting_row = rows.first()
        assert meeting_row is not None
        att_rows = await conn.execute(text("SELECT meeting_id FROM attachment WHERE id = 'att_a'"))
        assert att_rows.first().meeting_id == meeting_row.id


@pytest.mark.asyncio
async def test_generator_failed_returns_502(
    attachment_table, api_client_factory, migrated_engine: AsyncEngine
):
    """Generator parsing failure surfaces playbook.generation_failed 502."""
    await _seed_user(migrated_engine, "u_gen_fail2")
    gen = _StubPlaybookGenerator(error=PlaybookGenerationFailed("bad json"))
    async with api_client_factory(playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_gen_fail2"},
            json={
                "title": "Q3",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "calendar_event_id": "gcal_evt_42",
                "attachments": [],
            },
        )
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "playbook.generation_failed"
