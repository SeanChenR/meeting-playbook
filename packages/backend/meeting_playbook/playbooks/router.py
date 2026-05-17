"""Playbook REST router — GET (auto-create) + PUT (full upsert).

Per spec (slice-04-playbook-editor):
- Both endpoints scope by `MeetingRepository.get_for_user`; cross-user
  access returns 404 + `error_code: meeting.not_found` (no existence leak,
  reusing the slice-03 contract).
- GET auto-creates an empty playbook on first read so the UI always sees
  an editable surface.
- PUT performs a full upsert; missing fields are defaulted to '' by
  Pydantic (PlaybookUpsert).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.attachments.multimodal_context import (
    EMPTY_SET_SNAPSHOT_HASH,
    compute_attachment_snapshot_hash,
)
from meeting_playbook.attachments.repository import AttachmentRepository
from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.calendar.dependencies import get_playbook_generator_dependency
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_email_dependency,
    get_user_id_dependency,
    get_user_name_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.playbook_generation.generator import (
    PlaybookGenerationFailed,
    PlaybookGenerationTimeout,
    PlaybookGenerator,
)
from meeting_playbook.playbooks.repository import PlaybookRepository
from meeting_playbook.playbooks.schemas import PlaybookRead, PlaybookUpsert

router = APIRouter(prefix="/api/meetings", tags=["playbooks"])


def _meeting_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
    )


@router.get("/{meeting_id}/playbook", response_model=PlaybookRead)
async def get_playbook(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    repo = PlaybookRepository(session)
    playbook = await repo.get_or_create_for_meeting(meeting_id)

    # Slice-20c: compute is_stale by hashing the live attachment set and
    # comparing against the snapshot persisted at generation time.
    attachments = await AttachmentRepository(session).list_for_meeting_internal(
        meeting_id=meeting_id,
    )
    current_hash = (
        compute_attachment_snapshot_hash(list(attachments))
        if attachments
        else EMPTY_SET_SNAPSHOT_HASH
    )
    stored = playbook.attachment_hash_snapshot or EMPTY_SET_SNAPSHOT_HASH
    is_stale = stored != current_hash

    body = PlaybookRead.model_validate(playbook).model_copy(update={"is_stale": is_stale})
    return body


@router.put("/{meeting_id}/playbook", response_model=PlaybookRead)
async def put_playbook(
    meeting_id: str,
    body: PlaybookUpsert,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    payload = body.model_dump()
    saved = await PlaybookRepository(session).upsert_for_meeting(meeting_id, payload)
    return PlaybookRead.model_validate(saved)


def _synthesize_calendar_event(meeting: Any, viewer_email: str) -> CalendarEvent:
    """Build a minimal CalendarEvent from a meeting row for regenerate flows.

    Manually-created meetings have no real Google Calendar event; the
    generator's prompt builder only needs a few text fields. We populate
    title / start / end / attendees from what the meeting row carries
    and leave description blank.
    """
    return CalendarEvent(
        id=meeting.calendar_event_id or f"synthetic_{meeting.id}",
        title=meeting.title,
        start=meeting.scheduled_start_at.isoformat() if meeting.scheduled_start_at else "",
        end=meeting.scheduled_end_at.isoformat() if meeting.scheduled_end_at else "",
        attendees=[meeting.counterparty_display_name],
        description="",
        organizer=meeting.me_display_name,
        organizer_email=viewer_email,
    )


def _generator_error_to_http(exc: Exception) -> HTTPException:
    """Translate generator errors into stable HTTP envelopes."""
    if isinstance(exc, PlaybookGenerationTimeout):
        code, message = "playbook.generation_timeout", "Playbook regeneration timed out"
    else:
        code, message = "playbook.generation_failed", str(exc) or "Playbook regeneration failed"
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"error_code": code, "message": message},
    )


@router.post("/{meeting_id}/playbook/regenerate", response_model=PlaybookRead)
async def regenerate_playbook(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    user_email: Annotated[str, Depends(get_user_email_dependency)],
    user_name: Annotated[str, Depends(get_user_name_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    generator: Annotated[PlaybookGenerator, Depends(get_playbook_generator_dependency)],
) -> PlaybookRead:
    """Slice-20c regenerate: re-run the generator with the live attachment set.

    Used by the "Regenerate" button on the stale-banner. Fetches the
    current attachments, calls the multimodal LLM path, and persists
    the new draft alongside the fresh `attachment_hash_snapshot` so the
    banner clears.
    """
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    attachments = await AttachmentRepository(session).list_for_meeting_internal(
        meeting_id=meeting_id,
    )
    event = _synthesize_calendar_event(meeting, viewer_email=user_email)

    try:
        draft = await generator.generate(
            event,
            viewer_email=user_email,
            viewer_name=user_name,
            attachment_refs=list(attachments),
        )
    except (PlaybookGenerationTimeout, PlaybookGenerationFailed) as exc:
        raise _generator_error_to_http(exc) from exc

    snapshot = (
        compute_attachment_snapshot_hash(list(attachments))
        if attachments
        else EMPTY_SET_SNAPSHOT_HASH
    )
    payload: dict[str, object] = {**draft, "attachment_hash_snapshot": snapshot}
    # Slice-23: regenerate path goes through snapshot_then_upsert so the
    # row's prior `free_form_markdown` / `updated_at` /
    # `attachment_hash_snapshot` land in `previous_*` before the new
    # draft overwrites them. user-save (`PUT /playbook`) still uses the
    # plain `upsert_for_meeting`.
    saved = await PlaybookRepository(session).snapshot_then_upsert(
        meeting_id,
        payload,  # type: ignore[arg-type]
    )
    body = PlaybookRead.model_validate(saved).model_copy(update={"is_stale": False})
    return body


def _no_previous_version() -> HTTPException:
    """Stable envelope for the 404 when previous_* is NULL.

    Both `discard_previous` and `restore_previous` raise this. The
    frontend looks up `playbook.no_previous_version` via the locale
    error map (errors.playbook.no_previous_version).
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "playbook.no_previous_version",
            "message": "No previous playbook version to act on",
        },
    )


@router.post(
    "/{meeting_id}/playbook/discard_previous",
    response_model=PlaybookRead,
)
async def discard_previous_playbook(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    """Slice-23: clear the previous-version snapshot ("accept new draft").

    Per design D3: two POST endpoints (not a PATCH with action verb) so
    each path has its own OpenAPI / test surface and matches the
    existing `regenerate` style.
    """
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    updated = await PlaybookRepository(session).discard_previous(meeting_id)
    if updated is None:
        raise _no_previous_version()
    return PlaybookRead.model_validate(updated)


@router.post(
    "/{meeting_id}/playbook/restore_previous",
    response_model=PlaybookRead,
)
async def restore_previous_playbook(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    """Slice-23: swap the previous-version snapshot back into the current draft.

    Per design D3 + spec `playbook-versioning`: atomic swap of
    `previous_free_form_markdown` → `free_form_markdown` and matching
    `attachment_hash_snapshot`, then clears the snapshot.
    """
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    updated = await PlaybookRepository(session).restore_previous(meeting_id)
    if updated is None:
        raise _no_previous_version()
    return PlaybookRead.model_validate(updated)
