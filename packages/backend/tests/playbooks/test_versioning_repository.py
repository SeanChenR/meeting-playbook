"""PlaybookRepository versioning behavior — slice-23 task 1.3 / 1.4 / 1.5.

Covers:
- `snapshot_then_upsert` — atomically snapshots the prior row's
  `free_form_markdown` / `updated_at` / `attachment_hash_snapshot` into
  the `previous_*` columns, then upserts the new payload (design D2).
- `discard_previous` — clears the three `previous_*` columns without
  touching the current draft (spec `playbook-versioning`:
  "POST .../discard_previous SHALL clear the snapshot...").
- `restore_previous` — swaps `previous_*` back into the current columns
  and clears the snapshot (spec `playbook-versioning`:
  "POST .../restore_previous SHALL swap the snapshot back...").
- `upsert_for_meeting` (existing user-save path) MUST NOT touch the
  `previous_*` columns (spec `playbook-management`:
  "User-save upsert preserves the previous-version snapshot").
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.playbooks.repository import (
    PlaybookRepository,
    PlaybookUpsertPayload,
)


async def _seed_user_and_meeting(session: AsyncSession, *, meeting_id: str) -> None:
    """Insert a user + meeting that the playbook FK can satisfy."""
    user_id = f"u_{meeting_id}"
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, :name, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": user_id, "name": user_id, "email": f"{user_id}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, :uid, 'T', 'C', 'M')
            """
        ),
        {"mid": meeting_id, "uid": user_id},
    )
    await session.commit()


def _full_payload(**overrides: str) -> PlaybookUpsertPayload:
    base: PlaybookUpsertPayload = {
        "free_form_markdown": "",
        "objective": "",
        "counterparty_profile": "",
        "anticipated_topics": "",
        "anticipated_objections": "",
        "talking_points": "",
        "red_lines": "",
    }
    for k, v in overrides.items():
        base[k] = v  # type: ignore[literal-required]
    return base


# ─── 1.3 snapshot_then_upsert ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_then_upsert_existing_row(db_session: AsyncSession) -> None:
    """Existing row: snapshot captures v1 fields before v2 overwrites them."""
    await _seed_user_and_meeting(db_session, meeting_id="m_snap_existing")
    repo = PlaybookRepository(db_session)

    # First write: v1 with a known attachment hash snapshot.
    await repo.upsert_for_meeting(
        "m_snap_existing",
        _full_payload(
            free_form_markdown="v1",
            attachment_hash_snapshot="hash-A",  # type: ignore[typeddict-item]
        ),
    )
    v1 = await repo.get_or_create_for_meeting("m_snap_existing")
    assert v1.free_form_markdown == "v1"
    assert v1.attachment_hash_snapshot == "hash-A"
    v1_updated_at = v1.updated_at

    await asyncio.sleep(0.01)  # ensure updated_at advances on next write

    # Second write goes through snapshot_then_upsert.
    saved = await repo.snapshot_then_upsert(
        "m_snap_existing",
        _full_payload(
            free_form_markdown="v2",
            attachment_hash_snapshot="hash-B",  # type: ignore[typeddict-item]
        ),
    )

    assert saved.free_form_markdown == "v2"
    assert saved.attachment_hash_snapshot == "hash-B"
    assert saved.previous_free_form_markdown == "v1"
    assert saved.previous_attachment_hash_snapshot == "hash-A"
    # The snapshot's updated_at is the prior row's updated_at, not now().
    assert saved.previous_updated_at == v1_updated_at
    assert saved.updated_at > v1_updated_at


@pytest.mark.asyncio
async def test_snapshot_then_upsert_first_insert(db_session: AsyncSession) -> None:
    """No prior row: snapshot step is a no-op; previous_* remain NULL."""
    await _seed_user_and_meeting(db_session, meeting_id="m_snap_fresh")
    repo = PlaybookRepository(db_session)

    # No call to get_or_create — go straight through snapshot_then_upsert.
    saved = await repo.snapshot_then_upsert(
        "m_snap_fresh",
        _full_payload(
            free_form_markdown="first-ever",
            attachment_hash_snapshot="hash-X",  # type: ignore[typeddict-item]
        ),
    )
    assert saved.free_form_markdown == "first-ever"
    assert saved.attachment_hash_snapshot == "hash-X"
    assert saved.previous_free_form_markdown is None
    assert saved.previous_updated_at is None
    assert saved.previous_attachment_hash_snapshot is None


@pytest.mark.asyncio
async def test_user_save_upsert_preserves_snapshot(db_session: AsyncSession) -> None:
    """upsert_for_meeting (user-save path) MUST NOT touch previous_*.

    Covers spec `playbook-management` requirement
    "User-save upsert preserves the previous-version snapshot".
    """
    await _seed_user_and_meeting(db_session, meeting_id="m_user_save")
    repo = PlaybookRepository(db_session)

    # Seed v1, then snapshot_then_upsert to v2 so previous_* = v1's values.
    await repo.upsert_for_meeting(
        "m_user_save",
        _full_payload(
            free_form_markdown="v1",
            attachment_hash_snapshot="hash-A",  # type: ignore[typeddict-item]
        ),
    )
    await repo.snapshot_then_upsert(
        "m_user_save",
        _full_payload(
            free_form_markdown="v2",
            attachment_hash_snapshot="hash-B",  # type: ignore[typeddict-item]
        ),
    )

    # Capture snapshot state.
    before = await repo.get_or_create_for_meeting("m_user_save")
    assert before.previous_free_form_markdown == "v1"
    before_prev_updated_at = before.previous_updated_at
    before_prev_attachment = before.previous_attachment_hash_snapshot

    # User-save path edits free_form_markdown — previous_* MUST be untouched.
    await asyncio.sleep(0.01)
    after = await repo.upsert_for_meeting(
        "m_user_save",
        _full_payload(free_form_markdown="v2-edited"),
    )
    assert after.free_form_markdown == "v2-edited"
    assert after.previous_free_form_markdown == "v1"
    assert after.previous_updated_at == before_prev_updated_at
    assert after.previous_attachment_hash_snapshot == before_prev_attachment


# ─── 1.4 discard_previous ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discard_previous_clears_snapshot(db_session: AsyncSession) -> None:
    """discard_previous nulls the three previous_* columns; other fields unchanged."""
    await _seed_user_and_meeting(db_session, meeting_id="m_discard_yes")
    repo = PlaybookRepository(db_session)

    await repo.upsert_for_meeting(
        "m_discard_yes",
        _full_payload(
            free_form_markdown="v1",
            attachment_hash_snapshot="hash-A",  # type: ignore[typeddict-item]
        ),
    )
    await repo.snapshot_then_upsert(
        "m_discard_yes",
        _full_payload(
            free_form_markdown="v2",
            attachment_hash_snapshot="hash-B",  # type: ignore[typeddict-item]
        ),
    )

    discarded = await repo.discard_previous("m_discard_yes")
    assert discarded is not None
    assert discarded.previous_free_form_markdown is None
    assert discarded.previous_updated_at is None
    assert discarded.previous_attachment_hash_snapshot is None
    # Current draft unchanged.
    assert discarded.free_form_markdown == "v2"
    assert discarded.attachment_hash_snapshot == "hash-B"


@pytest.mark.asyncio
async def test_discard_previous_returns_none_when_no_snapshot(
    db_session: AsyncSession,
) -> None:
    """When previous_free_form_markdown is NULL, discard returns None."""
    await _seed_user_and_meeting(db_session, meeting_id="m_discard_no")
    repo = PlaybookRepository(db_session)

    # Seed a fresh row with no snapshot ever taken.
    await repo.upsert_for_meeting(
        "m_discard_no",
        _full_payload(
            free_form_markdown="only-version",
            attachment_hash_snapshot="hash-only",  # type: ignore[typeddict-item]
        ),
    )

    result = await repo.discard_previous("m_discard_no")
    assert result is None


# ─── 1.5 restore_previous ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_previous_swaps_snapshot_in(db_session: AsyncSession) -> None:
    """restore_previous: previous_* ↔ current, then previous_* cleared."""
    await _seed_user_and_meeting(db_session, meeting_id="m_restore_yes")
    repo = PlaybookRepository(db_session)

    # Build a row at v2 with previous = v1.
    await repo.upsert_for_meeting(
        "m_restore_yes",
        _full_payload(
            free_form_markdown="v1",
            objective="obj-v1",
            attachment_hash_snapshot="hash-A",  # type: ignore[typeddict-item]
        ),
    )
    await repo.snapshot_then_upsert(
        "m_restore_yes",
        _full_payload(
            free_form_markdown="v2",
            objective="obj-v2",
            attachment_hash_snapshot="hash-B",  # type: ignore[typeddict-item]
        ),
    )
    before_restore = await repo.get_or_create_for_meeting("m_restore_yes")
    before_updated_at = before_restore.updated_at

    await asyncio.sleep(0.01)
    restored = await repo.restore_previous("m_restore_yes")
    assert restored is not None
    assert restored.free_form_markdown == "v1"
    assert restored.attachment_hash_snapshot == "hash-A"
    # 6 structured fields not snapshotted → restore leaves them alone.
    assert restored.objective == "obj-v2"
    # previous_* cleared.
    assert restored.previous_free_form_markdown is None
    assert restored.previous_updated_at is None
    assert restored.previous_attachment_hash_snapshot is None
    # updated_at bumped on restore.
    assert restored.updated_at > before_updated_at
    assert restored.updated_at.tzinfo is not None  # timezone-aware


@pytest.mark.asyncio
async def test_restore_previous_returns_none_when_no_snapshot(
    db_session: AsyncSession,
) -> None:
    """When previous_free_form_markdown is NULL, restore returns None."""
    await _seed_user_and_meeting(db_session, meeting_id="m_restore_no")
    repo = PlaybookRepository(db_session)

    await repo.upsert_for_meeting(
        "m_restore_no",
        _full_payload(free_form_markdown="only"),
    )
    result = await repo.restore_previous("m_restore_no")
    assert result is None


@pytest.mark.asyncio
async def test_restore_previous_returns_none_when_row_missing(
    db_session: AsyncSession,
) -> None:
    """No playbook row at all → restore returns None (not a crash)."""
    await _seed_user_and_meeting(db_session, meeting_id="m_restore_missing")
    repo = PlaybookRepository(db_session)
    # Intentionally do not create a playbook row.
    assert await repo.restore_previous("m_restore_missing") is None


# Keep a reference to datetime so the test module doesn't get linted for
# an unused import — restore_previous bumps updated_at to a tz-aware UTC.
_ = datetime
_ = UTC
