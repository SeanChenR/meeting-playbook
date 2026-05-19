"""Tag REST router — slice-17 tasks 3.1 / 3.2 / 3.3.

Endpoints:
- `GET    /api/tags`                                  — list user's tags
- `POST   /api/tags`                                  — create
- `PATCH  /api/tags/{tag_id}`                         — rename / recolor
- `DELETE /api/tags/{tag_id}`                         — hard delete (FK cascades junction)
- `POST   /api/meetings/{meeting_id}/tags`            — attach (≤ 10/meeting)
- `DELETE /api/meetings/{meeting_id}/tags/{tag_id}`   — detach (idempotent)

Error envelope (per slice-02 contract):
- 404 with body `{"error_code": "tag.not_found"}` for cross-user or missing rows
  (does NOT distinguish "not yours" from "missing").
- 422 with body `{"error_code": "<code>", "message": ...}` for validation issues:
  - `tag.name_required`  — name blank / whitespace-only
  - `tag.name_taken`     — `(user_id, lower(name))` collision
  - `tag.invalid_color`  — color not in palette
  - `tag.too_many_for_meeting` — 11th attach (message contains `current_count`)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.tags.repository import (
    InvalidTagColor,
    InvalidTagName,
    TagLimitExceeded,
    TagNameTaken,
    TagRepository,
    TagWithMeta,
)

router = APIRouter(tags=["tags"])


class TagCreateBody(BaseModel):
    name: str = Field(min_length=1)
    color: str = Field(min_length=1)


class TagPatchBody(BaseModel):
    name: str | None = Field(default=None)
    color: str | None = Field(default=None)


class MeetingAttachBody(BaseModel):
    tag_id: str = Field(min_length=1)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "tag.not_found", "message": "Tag not found"},
    )


def _meeting_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
    )


def _serialize_tag(tag: TagWithMeta, *, include_count: bool = False) -> dict:
    """Serialize a `TagWithMeta` from the repository."""
    payload = {
        "id": tag.id,
        "user_id": tag.user_id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
    }
    if include_count and tag.meeting_count is not None:
        payload["meeting_count"] = tag.meeting_count
    return payload


@router.get("/api/tags")
async def list_tags(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    with_meeting_count: bool = False,
) -> list[dict]:
    repo = TagRepository(session)
    tags = await repo.list_for_user(user_id=user_id, with_meeting_count=with_meeting_count)
    return [_serialize_tag(t, include_count=with_meeting_count) for t in tags]


@router.post("/api/tags", status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreateBody,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    repo = TagRepository(session)
    try:
        tag = await repo.create(user_id=user_id, name=body.name, color=body.color)
    except InvalidTagName as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.name_required", "message": str(exc)},
        ) from exc
    except InvalidTagColor as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.invalid_color", "message": str(exc)},
        ) from exc
    except TagNameTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.name_taken", "message": str(exc)},
        ) from exc

    return {
        "id": tag.id,
        "user_id": tag.user_id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
    }


@router.patch("/api/tags/{tag_id}")
async def patch_tag(
    tag_id: str,
    body: TagPatchBody,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    repo = TagRepository(session)
    try:
        tag = await repo.update(user_id=user_id, tag_id=tag_id, name=body.name, color=body.color)
    except InvalidTagName as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.name_required", "message": str(exc)},
        ) from exc
    except InvalidTagColor as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.invalid_color", "message": str(exc)},
        ) from exc
    except TagNameTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "tag.name_taken", "message": str(exc)},
        ) from exc

    if tag is None:
        raise _not_found()
    return {
        "id": tag.id,
        "user_id": tag.user_id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
    }


@router.delete("/api/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    repo = TagRepository(session)
    deleted = await repo.delete(user_id=user_id, tag_id=tag_id)
    if not deleted:
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/meetings/{meeting_id}/tags", status_code=status.HTTP_201_CREATED)
async def attach_tag(
    meeting_id: str,
    body: MeetingAttachBody,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    repo = TagRepository(session)
    # Verify meeting ownership BEFORE the repo call so we can return the
    # canonical `meeting.not_found` error code instead of `tag.not_found`.
    meeting_repo = MeetingRepository(session)
    meeting = await meeting_repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()
    tag = await repo.get_for_user(user_id=user_id, tag_id=body.tag_id)
    if tag is None:
        raise _not_found()
    try:
        row = await repo.attach(user_id=user_id, meeting_id=meeting_id, tag_id=body.tag_id)
    except TagLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "tag.too_many_for_meeting",
                "message": (
                    f"Meeting already has {exc.current_count} tags "
                    "(max 10); detach one before adding another."
                ),
            },
        ) from exc
    except LookupError as exc:
        raise _not_found() from exc

    return {
        "meeting_id": row.meeting_id,
        "tag_id": row.tag_id,
        "attached_at": row.attached_at.isoformat(),
    }


@router.delete(
    "/api/meetings/{meeting_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_tag(
    meeting_id: str,
    tag_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    repo = TagRepository(session)
    await repo.detach(user_id=user_id, meeting_id=meeting_id, tag_id=tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
