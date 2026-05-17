"""Playbook router tests for slice-23 endpoints (regenerate / discard / restore).

Covers spec requirements:
- `playbook-generation`: regenerate endpoint persists via snapshot-then-upsert
- `playbook-versioning`: discard_previous / restore_previous endpoint contracts

Tests use a stub PlaybookGenerator so the multimodal LLM path is not exercised
— the slice-20c multimodal contract is verified by the existing integration
test under tests/integration/test_playbook_with_attachments.py.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.calendar.dependencies import get_playbook_generator_dependency
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.playbook_generation.generator import CONTENT_FIELDS, PlaybookGenerator
from meeting_playbook.server import create_app


class _StubGenerator:
    """Mimics PlaybookGenerator.generate without touching Vertex AI.

    Returns a fixed dict whose keys match CONTENT_FIELDS so the router's
    `**draft` spread works unchanged.
    """

    def __init__(self, draft: dict[str, str] | None = None) -> None:
        self._draft = draft or {field: f"regen-{field}" for field in CONTENT_FIELDS}
        # `free_form_markdown` defaulting to "regen-free_form_markdown" keeps
        # the assertions readable: tests can compare against the literal.

    async def generate(self, *args: object, **kwargs: object) -> dict[str, str]:
        return dict(self._draft)


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override
    app.dependency_overrides[get_playbook_generator_dependency] = lambda: _StubGenerator()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


async def _seed_user_and_meeting(engine: AsyncEngine, user_id: str, meeting_id: str) -> None:
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
        await conn.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES (:mid, :uid, 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )


async def _seed_playbook_row(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    free_form_markdown: str = "v1",
    attachment_hash_snapshot: str | None = "hash-A",
    previous_free_form_markdown: str | None = None,
    previous_attachment_hash_snapshot: str | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO playbook
                  (id, meeting_id, free_form_markdown,
                   objective, counterparty_profile, anticipated_topics,
                   anticipated_objections, talking_points, red_lines,
                   created_at, updated_at, attachment_hash_snapshot,
                   previous_free_form_markdown, previous_attachment_hash_snapshot,
                   previous_updated_at)
                VALUES
                  (:pid, :mid, :ffm,
                   '', '', '', '', '', '',
                   now(), now(), :hash,
                   :prev_ffm, :prev_hash, :prev_updated)
                """
            ),
            {
                "pid": f"pb_{meeting_id}",
                "mid": meeting_id,
                "ffm": free_form_markdown,
                "hash": attachment_hash_snapshot,
                "prev_ffm": previous_free_form_markdown,
                "prev_hash": previous_attachment_hash_snapshot,
                "prev_updated": datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
                if previous_free_form_markdown is not None
                else None,
            },
        )


# ─── 2.2 regenerate snapshots prior version ──────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_against_existing_row_snapshots_prior_version(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec `playbook-generation` scenario:
    Regenerate against existing playbook snapshots the prior version.
    """
    await _seed_user_and_meeting(migrated_engine, "u_regen_existing", "m_regen_existing")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_regen_existing",
        free_form_markdown="draft v1",
        attachment_hash_snapshot="hash-A",
    )

    resp = await api_client.post(
        "/api/meetings/m_regen_existing/playbook/regenerate",
        headers={"X-User-Id": "u_regen_existing"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # New draft persisted.
    assert body["free_form_markdown"] == "regen-free_form_markdown"
    # Snapshot captured the prior values.
    assert body["previous_free_form_markdown"] == "draft v1"
    assert body["has_previous_version"] is True


@pytest.mark.asyncio
async def test_regenerate_on_first_ever_run_has_no_snapshot(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec `playbook-generation` scenario:
    First-ever regenerate has no snapshot to capture.
    """
    await _seed_user_and_meeting(migrated_engine, "u_regen_first", "m_regen_first")
    # No playbook row exists yet.

    resp = await api_client.post(
        "/api/meetings/m_regen_first/playbook/regenerate",
        headers={"X-User-Id": "u_regen_first"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["free_form_markdown"] == "regen-free_form_markdown"
    assert body["previous_free_form_markdown"] is None
    assert body["has_previous_version"] is False


# ─── 2.3 discard_previous endpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_discard_with_snapshot_returns_200(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: Discard with snapshot present clears it."""
    await _seed_user_and_meeting(migrated_engine, "u_discard_yes", "m_discard_yes")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_discard_yes",
        free_form_markdown="v2",
        previous_free_form_markdown="v1",
        previous_attachment_hash_snapshot="hash-A",
    )

    resp = await api_client.post(
        "/api/meetings/m_discard_yes/playbook/discard_previous",
        headers={"X-User-Id": "u_discard_yes"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["free_form_markdown"] == "v2"
    assert body["previous_free_form_markdown"] is None
    assert body["has_previous_version"] is False


@pytest.mark.asyncio
async def test_discard_without_snapshot_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: Discard without snapshot returns 404."""
    await _seed_user_and_meeting(migrated_engine, "u_discard_no", "m_discard_no")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_discard_no",
        free_form_markdown="only-version",
    )

    resp = await api_client.post(
        "/api/meetings/m_discard_no/playbook/discard_previous",
        headers={"X-User-Id": "u_discard_no"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "playbook.no_previous_version"


@pytest.mark.asyncio
async def test_discard_cross_user_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: Discard against another user's meeting returns 404 meeting.not_found."""
    # Meeting owned by user B, snapshot present.
    await _seed_user_and_meeting(migrated_engine, "u_discard_owner", "m_discard_other")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_discard_other",
        free_form_markdown="owner v2",
        previous_free_form_markdown="owner v1",
    )

    resp = await api_client.post(
        "/api/meetings/m_discard_other/playbook/discard_previous",
        headers={"X-User-Id": "u_discard_attacker"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"
    # No leak of the inner snapshot state.
    flat = json.dumps(body).lower()
    assert "owner v1" not in flat
    assert "owner v2" not in flat


# ─── 2.4 restore_previous endpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_with_snapshot_swaps_in_previous(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: Restore with snapshot present swaps it in."""
    await _seed_user_and_meeting(migrated_engine, "u_restore_yes", "m_restore_yes")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_restore_yes",
        free_form_markdown="v2",
        attachment_hash_snapshot="hash-B",
        previous_free_form_markdown="v1",
        previous_attachment_hash_snapshot="hash-A",
    )

    resp = await api_client.post(
        "/api/meetings/m_restore_yes/playbook/restore_previous",
        headers={"X-User-Id": "u_restore_yes"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["free_form_markdown"] == "v1"
    assert body["previous_free_form_markdown"] is None
    assert body["has_previous_version"] is False


@pytest.mark.asyncio
async def test_restore_without_snapshot_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: Restore without snapshot returns 404."""
    await _seed_user_and_meeting(migrated_engine, "u_restore_no", "m_restore_no")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_restore_no",
        free_form_markdown="only",
    )

    resp = await api_client.post(
        "/api/meetings/m_restore_no/playbook/restore_previous",
        headers={"X-User-Id": "u_restore_no"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "playbook.no_previous_version"


@pytest.mark.asyncio
async def test_restore_cross_user_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Spec scenario: cross-user restore returns 404 meeting.not_found."""
    await _seed_user_and_meeting(migrated_engine, "u_restore_owner", "m_restore_other")
    await _seed_playbook_row(
        migrated_engine,
        meeting_id="m_restore_other",
        free_form_markdown="owner v2",
        previous_free_form_markdown="owner v1",
    )

    resp = await api_client.post(
        "/api/meetings/m_restore_other/playbook/restore_previous",
        headers={"X-User-Id": "u_restore_attacker"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"


# Keep an alias to PlaybookGenerator referenced so import linting stays happy.
_ = PlaybookGenerator
