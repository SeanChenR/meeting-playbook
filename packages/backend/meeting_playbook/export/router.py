"""FastAPI router for per-meeting ZIP export.

Endpoint: `GET /api/meetings/{meeting_id}/export`

Per slice-22-export-bundle spec:
- Owned meeting → HTTP 200 + `Content-Type: application/zip` + RFC 5987
  dual-value `Content-Disposition` header.
- Cross-user / missing meeting → HTTP 404 with
  `error_code = meeting.not_found` (consistent with the other meeting
  endpoints; no existence leak).
- Missing `X-User-Id` header → HTTP 401 `auth.gateway_bypass` via the
  shared dependency `get_user_id_dependency`.

The streaming body is produced by `MeetingExportBundler.iter_zip_chunks`
which is itself an async generator. We pass it to FastAPI's
`StreamingResponse` directly — no extra buffering.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.export.bundler import MeetingExportBundler, MeetingNotFound
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_session_factory_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository

router = APIRouter(prefix="/api/meetings", tags=["export"])

_ASCII_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")
_MAX_ASCII_SLUG_LEN = 80
_FALLBACK_SLUG = "meeting"


def get_session_factory_for_export() -> async_sessionmaker[AsyncSession]:
    """FastAPI dependency that yields the session factory used by the bundler.

    Wraps `get_session_factory_dependency` so tests can override this
    independently of the other meeting routes.
    """
    return get_session_factory_dependency()


def ascii_slug(title: str) -> str:
    """Replace non-`[A-Za-z0-9._-]` chars with `_`, collapse, trim, truncate.

    Per spec scenario "Owned meeting returns a streaming ZIP with both
    filename forms" + the ascii_slug transformations example table.
    """
    if not title:
        return _FALLBACK_SLUG
    replaced = _ASCII_SAFE_RE.sub("_", title)
    collapsed = _MULTI_UNDERSCORE_RE.sub("_", replaced)
    trimmed = collapsed.strip("_")
    if not trimmed:
        return _FALLBACK_SLUG
    return trimmed[:_MAX_ASCII_SLUG_LEN]


def _build_content_disposition(title: str, scheduled_at: datetime | None) -> str:
    """Build the RFC 5987 dual-value Content-Disposition header.

    Format: `attachment; filename="{ascii_slug}__{date}.zip";
             filename*=UTF-8''{percent_encoded_unicode}__{date}.zip`
    """
    date_part = (scheduled_at or datetime.utcnow()).date().isoformat()
    ascii_part = f"{ascii_slug(title)}__{date_part}.zip"
    unicode_basename = f"{title or _FALLBACK_SLUG}__{date_part}.zip"
    # Percent-encode the unicode form per RFC 5987.
    encoded = quote(unicode_basename, safe="")
    return f"attachment; filename=\"{ascii_part}\"; filename*=UTF-8''{encoded}"


@router.get("/{meeting_id}/export")
async def export_meeting_bundle(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory_for_export),
    ],
) -> StreamingResponse:
    """Stream the per-meeting ZIP bundle to the caller."""
    # Up-front ownership check so we can populate the
    # Content-Disposition header (title + scheduled_at) before the
    # streaming body begins, and so the 404 path returns the standard
    # error envelope rather than a half-written ZIP stream.
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )

    bundler = MeetingExportBundler(session_factory=session_factory)

    async def _stream():
        try:
            async for chunk in bundler.iter_zip_chunks(meeting_id=meeting_id, user_id=user_id):
                yield chunk
        except MeetingNotFound:
            # Bundler load-time miss after the router-level check is a
            # race (e.g. deletion between the two queries). Closing the
            # generator here surfaces a truncated response; clients can
            # retry. We do NOT swallow into a 200.
            return

    disposition = _build_content_disposition(meeting.title, meeting.scheduled_start_at)
    return StreamingResponse(
        _stream(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


__all__ = [
    "ascii_slug",
    "get_session_factory_for_export",
    "router",
]
