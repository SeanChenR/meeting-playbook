"""SessionRepository — write path for transcript_chunk + recording rows.

Per slice-06 design: this is the SOLE access path for the two new tables.
The session orchestrator inserts each transcript chunk BEFORE emitting it
to the WebSocket client, so a DB failure prevents an unconfirmed-write
state on the wire (per spec scenario "Failed insert prevents client
emission").
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.sessions.models import Recording, TranscriptChunk


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_chunks_for_meeting(self, meeting_id: str) -> list[TranscriptChunk]:
        """Historical transcript_chunk rows for a meeting, ordered chronologically."""
        result = await self._session.execute(
            select(TranscriptChunk)
            .where(TranscriptChunk.meeting_id == meeting_id)
            .order_by(TranscriptChunk.started_at.asc())
        )
        return list(result.scalars().all())

    async def list_chunks_last_60s(self, meeting_id: str) -> list[TranscriptChunk]:
        """Slice-08: rows from the last 60 seconds, ordered ascending.

        Used by the TacticalAdvisor's context assembly per ADR-0018. Window is
        a rolling SQL `now() - INTERVAL '60 seconds'`. Returns an empty list
        when the meeting has no chunks within the window (silent / just started).
        """
        from sqlalchemy import text as _text

        result = await self._session.execute(
            select(TranscriptChunk)
            .where(TranscriptChunk.meeting_id == meeting_id)
            .where(TranscriptChunk.started_at >= _text("now() - INTERVAL '60 seconds'"))
            .order_by(TranscriptChunk.started_at.asc())
        )
        return list(result.scalars().all())

    async def list_recordings_for_meeting(self, meeting_id: str) -> list[Recording]:
        """All recording rows for a meeting (slice-7: up to two — me + counterparty)."""
        result = await self._session.execute(
            select(Recording)
            .where(Recording.meeting_id == meeting_id)
            .order_by(Recording.stream.asc())
        )
        return list(result.scalars().all())

    async def insert_chunk(
        self,
        *,
        meeting_id: str,
        speaker: str,
        text_content: str,
        started_at: datetime,
        ended_at: datetime,
        asr_provider_used: str,
        confidence: float | None,
    ) -> TranscriptChunk:
        chunk = TranscriptChunk(
            id=f"tc_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            speaker=speaker,
            text=text_content,
            started_at=started_at,
            ended_at=ended_at,
            asr_provider_used=asr_provider_used,
            confidence=confidence,
            created_at=datetime.now(UTC),
        )
        self._session.add(chunk)
        # Commit per chunk (NOT just flush) so a server crash mid-session
        # does NOT lose every transcript chunk written so far. Tradeoff: more
        # round-trips, but durability beats throughput for ~1-chunk-per-10s
        # cadence.
        await self._session.commit()
        return chunk

    async def insert_recording(
        self,
        *,
        meeting_id: str,
        stream: str,
        file_path: str,
        bytes_size: int,
        started_at: datetime | None = None,
    ) -> Recording:
        # Slice-16: `recording.started_at` is NOT NULL — used by the
        # AudioRangeServer to anchor byte offsets to wall-clock. Callers
        # SHOULD pass the audio capture's first-sample timestamp; falling
        # back to now() preserves test ergonomics while still satisfying
        # the migration constraint.
        now = datetime.now(UTC)
        rec = Recording(
            id=f"rec_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            stream=stream,
            file_path=file_path,
            bytes=bytes_size,
            created_at=now,
            started_at=started_at or now,
        )
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def update_chunk_speakers(self, updates: list[tuple[str, str]]) -> int:
        """Slice-12: bulk-update `transcript_chunk.speaker` for a list of
        `(chunk_id, new_speaker)` pairs. Returns the number of rows updated.

        Called by the session finalize path after `SpeakerAttributionStrategy`
        has computed the final speaker labels for the meeting. Only invokes
        an UPDATE when the new value differs from the current value, so the
        dual-channel pass-through path costs at most one SELECT.
        """
        from sqlalchemy import update

        if not updates:
            return 0
        rows_changed = 0
        for chunk_id, new_speaker in updates:
            result = await self._session.execute(
                update(TranscriptChunk)
                .where(TranscriptChunk.id == chunk_id)
                .where(TranscriptChunk.speaker != new_speaker)
                .values(speaker=new_speaker)
            )
            rows_changed += result.rowcount or 0
        return rows_changed


__all__ = ["SessionRepository"]
