"""VoiceEnrollmentRepository — single-row-per-user persistence layer.

Slice-13 spec requirement "voice_enrollment table stores one embedding per
user". `upsert` replaces the existing row in place (no second row appended);
the FK CASCADE handles user-deletion cleanup at the database level so this
repo doesn't need a delete method.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.voice_enrollment.models import VoiceEnrollment


class VoiceEnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: str) -> VoiceEnrollment | None:
        result = await self._session.execute(
            select(VoiceEnrollment).where(VoiceEnrollment.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: str,
        sample_wav_path: str,
        embedding: bytes,
    ) -> VoiceEnrollment:
        """Insert or replace the per-user enrollment row.

        Uses PostgreSQL's `ON CONFLICT ... DO UPDATE` so re-enrollment is a
        single round-trip and the row count stays at 1 per user. `created_at`
        is bumped on every upsert so callers can see the freshness of the
        stored embedding.
        """
        now = datetime.now(UTC)
        stmt = (
            pg_insert(VoiceEnrollment)
            .values(
                user_id=user_id,
                sample_wav_path=sample_wav_path,
                embedding=embedding,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=[VoiceEnrollment.user_id],
                set_={
                    "sample_wav_path": sample_wav_path,
                    "embedding": embedding,
                    "created_at": now,
                },
            )
            .returning(VoiceEnrollment)
        )
        # `populate_existing` forces the session's identity map to refresh
        # the returned ORM instance with the post-update column values; without
        # it, a prior `get_for_user` call's cached instance would be returned
        # unchanged (and the test would see the OLD sample_wav_path).
        result = await self._session.execute(stmt, execution_options={"populate_existing": True})
        await self._session.commit()
        return result.scalar_one()
