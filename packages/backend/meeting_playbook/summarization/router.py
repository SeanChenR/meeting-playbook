"""Summary HTTP router — POST + GET /api/meetings/{id}/summary.

Per spec meeting-summary ADDED requirements:
- POST: spawn / regenerate (busy → 409, non-owner → 404)
- GET: 3 response shapes (Summary | pending | not_found)

The standard X-User-Id gateway-injected header is required on both;
ownership is verified via MeetingRepository.get_for_user (mirrors
slice-9 chat router).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.summarization import runtime
from meeting_playbook.summarization.repository import SummaryRepository

router = APIRouter(tags=["summary"])


def _meeting_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
    )


@router.post("/api/meetings/{meeting_id}/summary", status_code=202)
async def trigger_summary(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    """Spawn (or regenerate) the summary task for a meeting.

    Returns 202 + `{status: "pending"}` on successful spawn.
    Returns 409 + `{error_code: "summary.busy"}` when a task is already
    in-flight for this meeting.
    Returns 404 + `{error_code: "meeting.not_found"}` for non-owner.
    """
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    if runtime.is_pending(meeting_id):
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "summary.busy",
                "message": "A summary generation is already running for this meeting",
            },
        )

    spawned = await runtime.spawn_summary_task(meeting_id)
    if not spawned:
        # Race: between is_pending and spawn another caller spawned a task.
        # Treat the same as the precheck failure.
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "summary.busy",
                "message": "A summary generation is already running for this meeting",
            },
        )
    return {"status": "pending"}


@router.get("/api/meetings/{meeting_id}/summary")
async def get_summary(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    """Three response shapes: present / pending / not_found.

    (a) Row exists → 200 + full Summary + is_stale
    (b) No row but in-flight → 200 + `{status: "pending", generated_at: null}`
    (c) No row + not in-flight → 404 `summary.not_found`
    """
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    # Slice-20c: compute the live attachment-set hash and feed it to the
    # repository so `is_stale` reflects attachment churn alongside the
    # legacy transcript / playbook / chat timestamp signals.
    from meeting_playbook.attachments.multimodal_context import (
        EMPTY_SET_SNAPSHOT_HASH,
        compute_attachment_snapshot_hash,
    )
    from meeting_playbook.attachments.repository import AttachmentRepository

    attachments = await AttachmentRepository(session).list_for_meeting_internal(
        meeting_id=meeting_id,
    )
    current_hash = (
        compute_attachment_snapshot_hash(list(attachments))
        if attachments
        else EMPTY_SET_SNAPSHOT_HASH
    )

    summary = await SummaryRepository(session).get_with_stale_flag(
        meeting_id,
        current_attachment_snapshot_hash=current_hash,
    )
    if summary is not None:
        return {
            "id": summary.id,
            "meeting_id": summary.meeting_id,
            "markdown": summary.markdown,
            "generated_at": summary.generated_at.isoformat(),
            "is_stale": summary.is_stale,
        }

    if runtime.is_pending(meeting_id):
        return {"status": "pending", "generated_at": None}

    raise HTTPException(
        status_code=404,
        detail={
            "error_code": "summary.not_found",
            "message": "No summary has been generated for this meeting",
        },
    )
