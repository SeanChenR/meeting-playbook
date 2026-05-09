"""Schema assertions for the slice-06 migration `0003_create_session_tables`.

Per spec slice-06 ADDED requirements (transcript_chunk + recording schema +
meeting.updated_at column).
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_meeting_has_updated_at_column(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns("meeting"))
    names = {c["name"] for c in cols}
    assert "updated_at" in names


@pytest.mark.asyncio
async def test_transcript_chunk_table_shape(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns("transcript_chunk"))
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys("transcript_chunk"))
        checks = await conn.run_sync(lambda c: inspect(c).get_check_constraints("transcript_chunk"))
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("transcript_chunk"))

    names = {c["name"] for c in cols}
    expected = {
        "id",
        "meeting_id",
        "speaker",
        "text",
        "started_at",
        "ended_at",
        "asr_provider_used",
        "confidence",
        "created_at",
    }
    missing = expected - names
    assert not missing, f"transcript_chunk missing columns: {missing}"

    # FK to meeting.id with ON DELETE CASCADE.
    meeting_fks = [fk for fk in fks if fk.get("referred_table") == "meeting"]
    assert meeting_fks, "transcript_chunk must FK to meeting"
    assert meeting_fks[0]["options"].get("ondelete", "").upper() == "CASCADE"

    # Speaker CHECK accepts the three valid values.
    speaker_check = next((c for c in checks if c["name"] == "transcript_chunk_speaker_check"), None)
    assert speaker_check is not None
    sql = speaker_check["sqltext"].lower()
    for v in ("me", "counterparty", "system"):
        assert v in sql

    # Index on (meeting_id, started_at) for ordered queries.
    assert any(idx["column_names"] == ["meeting_id", "started_at"] for idx in indexes), (
        f"missing index, got: {[i['column_names'] for i in indexes]}"
    )


@pytest.mark.asyncio
async def test_recording_table_shape(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns("recording"))
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys("recording"))
        checks = await conn.run_sync(lambda c: inspect(c).get_check_constraints("recording"))
        uniques = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("recording"))

    names = {c["name"] for c in cols}
    expected = {
        "id",
        "meeting_id",
        "stream",
        "file_path",
        "bytes",
        "created_at",
    }
    missing = expected - names
    assert not missing, f"recording missing columns: {missing}"

    meeting_fks = [fk for fk in fks if fk.get("referred_table") == "meeting"]
    assert meeting_fks
    assert meeting_fks[0]["options"].get("ondelete", "").upper() == "CASCADE"

    stream_check = next((c for c in checks if c["name"] == "recording_stream_check"), None)
    assert stream_check is not None
    sql = stream_check["sqltext"].lower()
    for v in ("me", "counterparty"):
        assert v in sql

    # One recording row per (meeting, stream).
    assert any(set(u["column_names"]) == {"meeting_id", "stream"} for u in uniques)
