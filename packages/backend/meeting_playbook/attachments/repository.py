"""AttachmentRepository — the single access path for meeting_attachment rows.

Per slice-20a design:
- Every method takes `user_id` and joins through `meeting.user_id` so a
  non-owner can never read or mutate another user's attachments.
- Soft-delete is the canonical removal: `deleted_at = now()`; the row is
  preserved for audit. The file on disk is removed by the router (the
  repository stays I/O-free).
- IDs use `att_<token_urlsafe(16)>` so they sort lexicographically next to
  the existing `m_…` / `r_…` shapes used elsewhere in the codebase.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.attachments.models import AttachmentKind, MeetingAttachment
from meeting_playbook.meetings.models import Meeting


class AttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _meeting_belongs_to_user(self, *, meeting_id: str, user_id: str) -> bool:
        """True iff the meeting exists AND is owned by the given user."""
        result = await self._session.execute(
            select(Meeting.id).where(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_for_meeting_internal(self, *, meeting_id: str) -> list[MeetingAttachment]:
        """Return active attachments without an ownership check.

        Used by background workers (slice-20c snapshot computation in the
        summary runtime) that already operate on a trusted meeting id and
        run outside an HTTP request scope. NEVER call this from a router
        path — every user-facing request MUST go through
        `list_for_meeting(..., user_id=...)`.
        """
        result = await self._session.execute(
            select(MeetingAttachment)
            .where(
                MeetingAttachment.meeting_id == meeting_id,
                MeetingAttachment.deleted_at.is_(None),
            )
            .order_by(MeetingAttachment.uploaded_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_meeting(self, *, meeting_id: str, user_id: str) -> list[MeetingAttachment]:
        """Return only active (deleted_at IS NULL) rows for the meeting owner.

        Non-owners (or unknown meeting IDs) receive an empty list — the
        router maps this shape onto an HTTP 200 with empty `attachments`
        for owners, and a 404 for non-owners (via a separate ownership
        check before this call).
        """
        if not await self._meeting_belongs_to_user(meeting_id=meeting_id, user_id=user_id):
            return []
        result = await self._session.execute(
            select(MeetingAttachment)
            .where(
                MeetingAttachment.meeting_id == meeting_id,
                MeetingAttachment.deleted_at.is_(None),
            )
            .order_by(MeetingAttachment.uploaded_at.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        meeting_id: str,
        kind: AttachmentKind,
        original_name: str,
        file_path: str,
        bytes_: int,
    ) -> MeetingAttachment:
        """Insert a new row and return it.

        The caller MUST have already validated ownership + quota + whitelist.
        Repository stays validation-free so unit tests can wire it directly
        without re-running the router's checks.
        """
        att = MeetingAttachment(
            id=f"att_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            file_path=file_path,
            kind=kind,
            original_name=original_name,
            bytes=int(bytes_),
            uploaded_at=datetime.now(UTC),
            deleted_at=None,
        )
        self._session.add(att)
        await self._session.commit()
        await self._session.refresh(att)
        return att

    async def soft_delete(self, *, attachment_id: str, user_id: str) -> MeetingAttachment | None:
        """Flip `deleted_at` on the row when the user owns the parent meeting.

        Returns the refreshed row, or None when:
          - the attachment doesn't exist,
          - the parent meeting isn't owned by `user_id`, OR
          - the attachment is already soft-deleted (treated as "not found"
            from the API perspective — second DELETE → 404).
        """
        result = await self._session.execute(
            select(MeetingAttachment, Meeting)
            .join(Meeting, MeetingAttachment.meeting_id == Meeting.id)
            .where(
                MeetingAttachment.id == attachment_id,
                Meeting.user_id == user_id,
                MeetingAttachment.deleted_at.is_(None),
            )
        )
        row = result.first()
        if row is None:
            return None
        att: MeetingAttachment = row[0]
        att.deleted_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(att)
        return att

    async def get_for_download(
        self, *, attachment_id: str, user_id: str
    ) -> MeetingAttachment | None:
        """Return the active row when the user owns the parent meeting.

        Soft-deleted rows return None so the download endpoint surfaces 404
        (preventing access to rows whose file may have already been
        unlinked from disk).
        """
        result = await self._session.execute(
            select(MeetingAttachment)
            .join(Meeting, MeetingAttachment.meeting_id == Meeting.id)
            .where(
                MeetingAttachment.id == attachment_id,
                Meeting.user_id == user_id,
                MeetingAttachment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


__all__ = ["AttachmentRepository"]
