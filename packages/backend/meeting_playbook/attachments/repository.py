"""AttachmentRepository — the single access path for meeting_attachment rows.

Per slice-20a design:
- Every API path is scoped by `user_id`. Before slice-24 the scoping came
  from `JOIN meeting ON ... WHERE meeting.user_id = ?`; with slice-24 the
  table carries `user_id` directly so staged rows (meeting_id IS NULL)
  remain scoped to their uploader.
- Soft-delete is the canonical removal: `deleted_at = now()`; the row is
  preserved for audit. The file on disk is removed by the router (the
  repository stays I/O-free).
- IDs use `att_<token_urlsafe(16)>` so they sort lexicographically next to
  the existing `m_…` / `r_…` shapes used elsewhere in the codebase.

Slice-24 additions:
- `create(meeting_id=None, user_id=...)` accepts a staged row.
- `list_staged_for_user(user_id)` lists active staged rows for a user.
- `delete_staged(attachment_id, user_id)` soft-deletes ONLY a staged row
  owned by the given user; returns None for attached / cross-user rows.
- `count_staged_for_user(user_id)` returns `(file_count, total_bytes)` so
  the staging-upload handler can enforce per-user quota.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
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
        user_id: str,
        kind: AttachmentKind,
        original_name: str,
        file_path: str,
        bytes_: int,
        meeting_id: str | None = None,
        attachment_id: str | None = None,
    ) -> MeetingAttachment:
        """Insert a new row and return it.

        The caller MUST have already validated ownership + quota + whitelist.
        Repository stays validation-free so unit tests can wire it directly
        without re-running the router's checks.

        `meeting_id=None` produces a staged row (slice-24); `user_id` is
        required either way so the row always knows its owner.

        `attachment_id` is optional — when None we mint one here so existing
        unit tests don't need to pre-allocate. The upload path passes the
        pre-staged id so the on-disk filename matches the row id without a
        post-insert rename (see attachments/router.py upload handler).
        """
        att = MeetingAttachment(
            id=attachment_id or f"att_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            user_id=user_id,
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

        For staged rows (meeting_id IS NULL) callers MUST use
        `delete_staged` instead — this method only handles attached rows
        because the JOIN to `meeting` filters them out.
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

    # ─── Slice-24: staged (orphan) row support ────────────────────────

    async def list_staged_for_user(self, *, user_id: str) -> list[MeetingAttachment]:
        """List the user's active staged rows, oldest upload first.

        Used by `GET /api/attachments?status=pending` so the
        `<StagedAttachmentDropzone>` can render the current selection in
        upload order.
        """
        result = await self._session.execute(
            select(MeetingAttachment)
            .where(
                MeetingAttachment.user_id == user_id,
                MeetingAttachment.meeting_id.is_(None),
                MeetingAttachment.deleted_at.is_(None),
            )
            .order_by(MeetingAttachment.uploaded_at.asc())
        )
        return list(result.scalars().all())

    async def delete_staged(self, *, attachment_id: str, user_id: str) -> MeetingAttachment | None:
        """Soft-delete a staged row owned by the user.

        Returns the refreshed row on success, or None when:
          - no row matches the id, OR
          - the row is attached (`meeting_id IS NOT NULL`) — callers
            MUST use the meeting-scoped delete endpoint, OR
          - the row is owned by a different user, OR
          - the row is already soft-deleted.

        Cross-user / attached / not-found all collapse onto None so the
        router can respond 404 without leaking the distinction.
        """
        result = await self._session.execute(
            select(MeetingAttachment).where(
                MeetingAttachment.id == attachment_id,
                MeetingAttachment.user_id == user_id,
                MeetingAttachment.meeting_id.is_(None),
                MeetingAttachment.deleted_at.is_(None),
            )
        )
        att = result.scalar_one_or_none()
        if att is None:
            return None
        att.deleted_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(att)
        return att

    async def count_staged_for_user(self, *, user_id: str) -> tuple[int, int]:
        """Return `(file_count, total_bytes)` for the user's active staged rows.

        Used by the staging-upload handler to enforce the per-user quota
        (10 files / 60 MiB by design D6). `total_bytes` is `0` when no
        active staged rows exist (COALESCE on SUM).
        """
        result = await self._session.execute(
            select(
                func.count(MeetingAttachment.id),
                func.coalesce(func.sum(MeetingAttachment.bytes), 0),
            ).where(
                MeetingAttachment.user_id == user_id,
                MeetingAttachment.meeting_id.is_(None),
                MeetingAttachment.deleted_at.is_(None),
            )
        )
        row = result.one()
        return int(row[0]), int(row[1])


__all__ = ["AttachmentRepository"]
