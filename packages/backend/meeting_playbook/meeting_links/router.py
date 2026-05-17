"""FastAPI router for the meeting-links capability — slice-21 tasks 3.1-3.3.

Mounted under ``/api/meetings/{meeting_id}/links``. Every endpoint enforces
ownership before touching the link table:

- The URL's ``{meeting_id}`` must belong to the X-User-Id user (returns
  HTTP 404 ``meeting.not_found`` otherwise — no existence leak).
- POST additionally requires the body's ``to_meeting_id`` to belong to the
  same user.
- DELETE additionally requires the path's ``{meeting_id}`` to be one of the
  two meetings the link references — multi-layered check to block "borrowing
  your own meeting id on the path to delete someone else's link".

Errors follow the project ``{error_code, message}`` envelope convention.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meeting_links.repository import (
    MeetingLinkDuplicate,
    MeetingLinkRepository,
    MeetingLinkSelfReference,
)
from meeting_playbook.meeting_links.schemas import (
    MeetingLinkCreateRequest,
    MeetingLinkView,
)
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository

router = APIRouter(prefix="/api/meetings", tags=["meeting-links"])


# ─── Helpers ───────────────────────────────────────────────────────────


def _meeting_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
    )


def _link_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "meeting_link.not_found",
            "message": "Meeting link not found",
        },
    )


# ─── Endpoints ─────────────────────────────────────────────────────────


@router.get("/{meeting_id}/links")
async def list_meeting_links(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, list[MeetingLinkView]]:
    """Return every related-meeting link for ``meeting_id``.

    Per spec ``GET /api/meetings/{id}/links``:
    - Ownership-checks ``meeting_id`` first; cross-user / unknown → 404.
    - Each row is projected as "other-meeting perspective" by the repository.
    - Sorted by ``created_at`` DESC.
    """
    meetings = MeetingRepository(session)
    meeting = await meetings.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    links = await MeetingLinkRepository(session).list_for_meeting(meeting_id)
    return {"links": links}


@router.post("/{meeting_id}/links", status_code=status.HTTP_201_CREATED)
async def create_meeting_link(
    meeting_id: str,
    body: MeetingLinkCreateRequest,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, str]:
    """Create a related-meeting link between ``meeting_id`` and ``body.to_meeting_id``.

    Per spec ``POST /api/meetings/{id}/links``:
    - Both endpoints' meetings MUST belong to the current user (any miss → 404).
    - Self-reference → 422 ``meeting_link.self_reference``.
    - Duplicate pair (in either direction) → 409 ``meeting_link.duplicate``.
    - Success → 201 ``{link_id: UUID}``.
    """
    meetings = MeetingRepository(session)
    from_meeting = await meetings.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if from_meeting is None:
        raise _meeting_not_found()
    to_meeting = await meetings.get_for_user(user_id=user_id, meeting_id=body.to_meeting_id)
    if to_meeting is None:
        raise _meeting_not_found()

    # Application-level self-reference check up front — also catches the
    # `to_meeting_id == meeting_id` case where both ownership checks pass
    # but the link would violate the DB CHECK constraint.
    if body.to_meeting_id == meeting_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "meeting_link.self_reference",
                "message": "Cannot link a meeting to itself",
            },
        )

    links = MeetingLinkRepository(session)
    try:
        link = await links.create(from_meeting_id=meeting_id, to_meeting_id=body.to_meeting_id)
    except MeetingLinkDuplicate as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "meeting_link.duplicate",
                "message": "These meetings are already linked",
            },
        ) from exc
    except MeetingLinkSelfReference as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "meeting_link.self_reference",
                "message": "Cannot link a meeting to itself",
            },
        ) from exc

    return {"link_id": str(link.id)}


@router.delete(
    "/{meeting_id}/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_meeting_link(
    meeting_id: str,
    link_id: UUID,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    """Delete the link identified by ``link_id``.

    Per spec ``DELETE /api/meetings/{id}/links/{link_id}``:
    - The path's ``meeting_id`` must be one of the link's two endpoints AND
      must belong to the current user. Both checks together prevent
      "borrow another user's link_id with your own meeting id on the path".
    - Unknown / foreign link → 404 ``meeting_link.not_found`` (no leak).
    - Success → 204.
    """
    links = MeetingLinkRepository(session)
    link = await links.get(link_id)
    if link is None:
        raise _link_not_found()

    # Sanity check: path meeting_id must match one of the link's endpoints.
    if meeting_id not in (link.from_meeting_id, link.to_meeting_id):
        raise _link_not_found()

    # Ownership: at least one end of the link must be a meeting owned by the
    # current user, AND the path-provided meeting_id must specifically be
    # owned by them (the user is "deleting from their side").
    meetings = MeetingRepository(session)
    path_meeting = await meetings.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if path_meeting is None:
        raise _link_not_found()

    deleted = await links.delete(link_id)
    if not deleted:
        # Race — someone deleted it between `get` and `delete`. Treat as
        # idempotent and return 204 anyway (matches HTTP spirit; the row
        # is gone either way).
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
