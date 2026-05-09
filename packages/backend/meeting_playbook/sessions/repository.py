"""SessionRepository — write path for transcript_chunk + recording rows.

Per slice-06 design: this is the SOLE access path for the two new tables.
The session orchestrator inserts each transcript chunk BEFORE emitting it
to the WebSocket client, so a DB failure prevents an unconfirmed-write
state on the wire (per spec scenario "Failed insert prevents client
emission").
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

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
            created_at=datetime.now(timezone.utc),
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
    ) -> Recording:
        rec = Recording(
            id=f"rec_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            stream=stream,
            file_path=file_path,
            bytes=bytes_size,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(rec)
        await self._session.flush()
        return rec


__all__ = ["SessionRepository"]
