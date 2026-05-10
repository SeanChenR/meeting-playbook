"""Schema assertions for the slice-07 migration `0004_add_meeting_scheduled_times`.

Per spec slice-07 ADDED requirement (`Meeting carries optional scheduled start
and end timestamps`). The migration adds two nullable TIMESTAMPTZ columns to
the `meeting` table; existing rows are NOT backfilled.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_meeting_has_scheduled_start_at_column(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns("meeting"))
    by_name = {c["name"]: c for c in cols}
    assert "scheduled_start_at" in by_name, "migration 0004 must add scheduled_start_at"
    col = by_name["scheduled_start_at"]
    assert col["nullable"] is True, "scheduled_start_at must be nullable"
    # SQLAlchemy reports TIMESTAMP WITH TIME ZONE as TIMESTAMP with timezone=True
    coltype = col["type"]
    assert getattr(coltype, "timezone", False) is True, (
        f"scheduled_start_at must be TIMESTAMPTZ, got {coltype!r}"
    )


@pytest.mark.asyncio
async def test_meeting_has_scheduled_end_at_column(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns("meeting"))
    by_name = {c["name"]: c for c in cols}
    assert "scheduled_end_at" in by_name, "migration 0004 must add scheduled_end_at"
    col = by_name["scheduled_end_at"]
    assert col["nullable"] is True, "scheduled_end_at must be nullable"
    coltype = col["type"]
    assert getattr(coltype, "timezone", False) is True, (
        f"scheduled_end_at must be TIMESTAMPTZ, got {coltype!r}"
    )
