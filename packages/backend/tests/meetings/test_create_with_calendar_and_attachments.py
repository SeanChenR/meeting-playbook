"""Slice-20b + slice-24: `POST /api/meetings` with `calendar_event_id` + `attachments[]`.

Per spec deltas:
- `meeting-management` MODIFIED requirement "POST /api/meetings accepts an
  attachments list..." — ownership + meeting_id IS NULL validation BEFORE
  meeting create + physical file move + rollback on failure (slice-24).
- `meeting-management` MODIFIED requirement "Meeting carries an optional
  Calendar event reference" — calendar_event_id persists, triggers generator.
- `playbook-generation` ADDED requirement "Playbook generation is triggered
  by POST /api/meetings when calendar_event_id is supplied" — generator
  runs, playbook upserted; absent calendar_event_id = no generator call.

Slice-24 update: the test now uses the real `meeting_attachment` table
(produced by slice-20a migration 0016 + slice-24 migration 0019 adding
`user_id` + nullable `meeting_id`). The stand-in `attachment` DDL has
been retired — production code points at `meeting_attachment` only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
async def api_client_factory(migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch):
    """Build an httpx AsyncClient with the real backend wired to the test DB.

    Slice-24: also points `ATTACHMENT_DIR` at a per-test tmpdir so file
    moves are observable without touching the developer home folder.
    """
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ATTACHMENT_DIR", str(tmp_path))

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
    file_path: str = "/tmp/unused.pdf",
    bytes_: int = 100,
) -> None:
    """Insert a `meeting_attachment` row (staged when meeting_id is None)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting_attachment (
                    id, meeting_id, user_id, file_path, kind, original_name,
                    bytes, uploaded_at
                )
                VALUES (
                    :aid, :mid, :uid, :path, 'pdf', 'staged.pdf',
                    :bytes, now()
                )
                """
            ),
            {
                "aid": attachment_id,
                "mid": meeting_id,
                "uid": user_id,
                "path": file_path,
                "bytes": bytes_,
            },
        )


def _staging_path(tmp_root: Path, user_id: str, att_id: str, ext: str = ".pdf") -> Path:
    return tmp_root / "_staging" / user_id / f"{att_id}{ext}"


def _seed_staged_file(tmp_root: Path, user_id: str, att_id: str) -> Path:
    """Write a small placeholder file into the user's staging dir + return path."""
    path = _staging_path(tmp_root, user_id, att_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\nstaged-content\n")
    return path


# ─── Calendar event id triggers generator ───────────────────────────────────


@pytest.mark.asyncio
async def test_create_with_calendar_event_id_triggers_generator(
    api_client_factory, migrated_engine: AsyncEngine
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


@pytest.mark.asyncio
async def test_create_without_calendar_event_id_does_not_call_generator(
    api_client_factory, migrated_engine: AsyncEngine
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


# ─── Attachments write back meeting_id + slice-24 file move ────────────


@pytest.mark.asyncio
async def test_create_with_attachments_moves_files_to_meeting_dir(
    api_client_factory, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Slice-24: successful create physically moves staged files into the meeting dir."""
    await _seed_user(migrated_engine, "u_owner")
    staged_1 = _seed_staged_file(tmp_path, "u_owner", "att_1")
    staged_2 = _seed_staged_file(tmp_path, "u_owner", "att_2")
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_1",
        user_id="u_owner",
        meeting_id=None,
        file_path=str(staged_1),
    )
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_2",
        user_id="u_owner",
        meeting_id=None,
        file_path=str(staged_2),
    )

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

    # Files moved into ATTACHMENT_DIR/<meeting_id>/.
    assert not staged_1.exists(), "Original staging path must no longer exist"
    assert not staged_2.exists()
    meeting_dir = tmp_path / meeting_id
    assert meeting_dir.is_dir()
    moved_files = sorted(p.name for p in meeting_dir.iterdir())
    assert "att_1.pdf" in moved_files
    assert "att_2.pdf" in moved_files

    # Row updates: meeting_id set + file_path updated.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT id, meeting_id, file_path
                FROM meeting_attachment
                WHERE id IN ('att_1', 'att_2')
                ORDER BY id
                """
            )
        )
        records = list(rows)
    assert len(records) == 2
    for rec in records:
        assert rec.meeting_id == meeting_id
        assert str(meeting_dir) in rec.file_path


# ─── Other user's attachment is rejected ────────────────────────────────────


@pytest.mark.asyncio
async def test_attachment_owned_by_other_user_is_rejected_with_attachment_not_attachable(
    api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Attachment owned by another user is rejected with attachment.not_attachable."""
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_other",
        user_id="u_b",
        meeting_id=None,
    )

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
            text("SELECT user_id, meeting_id FROM meeting_attachment WHERE id = 'att_other'")
        )
        att = att_rows.first()
        assert att.user_id == "u_b"
        assert att.meeting_id is None


# ─── Already-attached attachment is rejected ────────────────────────────────


@pytest.mark.asyncio
async def test_already_attached_attachment_is_rejected(
    api_client_factory, migrated_engine: AsyncEngine
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
    api_client_factory, migrated_engine: AsyncEngine
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


# ─── Generator failure rolls back attach + meeting (slice-24 D5) ─────────


@pytest.mark.asyncio
async def test_generator_timeout_rolls_back_attach_step(
    api_client_factory, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Slice-24 D5: Playbook generator timeout MUST roll back attach + meeting.

    Per design "Attach 失敗的 rollback：move 回 staging":
    - The file is moved back to the original staging path.
    - The attachment row's meeting_id is reset to NULL + file_path
      points back to staging.
    - The meeting row is deleted so the user does not see a half-built
      meeting in their list.
    - The HTTP response carries the underlying generator error code
      (`playbook.generation_timeout`).
    """
    await _seed_user(migrated_engine, "u_gen_fail")
    staged = _seed_staged_file(tmp_path, "u_gen_fail", "att_a")
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_a",
        user_id="u_gen_fail",
        meeting_id=None,
        file_path=str(staged),
    )
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

    # File is back in the original staging location.
    assert staged.exists(), "Rollback MUST move the file back to staging"
    # Row's meeting_id reset to NULL + file_path restored to staging.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT meeting_id, file_path
                FROM meeting_attachment
                WHERE id = 'att_a'
                """
            )
        )
        row = rows.first()
        assert row is not None
        assert row.meeting_id is None
        assert row.file_path == str(staged)
        # Meeting row was rolled back (does not exist).
        m_rows = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_gen_fail"},
        )
        assert m_rows.first() is None, (
            "Rollback MUST delete the meeting row created during this request"
        )


@pytest.mark.asyncio
async def test_generator_failed_rolls_back_attach_step(
    api_client_factory, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Generator PlaybookGenerationFailed also rolls back attach + meeting."""
    await _seed_user(migrated_engine, "u_gen_fail2")
    staged = _seed_staged_file(tmp_path, "u_gen_fail2", "att_b")
    await _insert_attachment(
        migrated_engine,
        attachment_id="att_b",
        user_id="u_gen_fail2",
        meeting_id=None,
        file_path=str(staged),
    )
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
                "attachments": ["att_b"],
            },
        )
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "playbook.generation_failed"

    assert staged.exists(), "Rollback MUST restore the staging file"
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(text("SELECT meeting_id FROM meeting_attachment WHERE id = 'att_b'"))
        ).first()
        assert row.meeting_id is None
        m = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_gen_fail2"},
        )
        assert m.first() is None


@pytest.mark.asyncio
async def test_no_attachments_generator_failure_still_persists_meeting(
    api_client_factory, migrated_engine: AsyncEngine
):
    """When no attachments are in the request, generator failure still rolls back the meeting.

    Spec contract: the response surfaces `playbook.generation_timeout`
    AND the meeting row is rolled back so the user does not end up with
    a meeting that has no Playbook. (Slice-24 strengthens the prior
    slice-20b behaviour, which kept the meeting around.)
    """
    await _seed_user(migrated_engine, "u_no_att")
    gen = _StubPlaybookGenerator(error=PlaybookGenerationTimeout("60s"))
    async with api_client_factory(playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings",
            headers={"X-User-Id": "u_no_att"},
            json={
                "title": "Q3",
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
                "calendar_event_id": "gcal_evt_42",
                "attachments": [],
            },
        )
    assert resp.status_code == 504
    assert resp.json()["error_code"] == "playbook.generation_timeout"

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_no_att"},
        )
        assert rows.first() is None
