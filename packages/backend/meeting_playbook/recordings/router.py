"""Recording-index router — `GET /api/recordings` + `POST /api/recordings/batch-download`.

Per spec `recording-index` (P4 IA refactor):
- The list endpoint surfaces every Recording inside the active Recording
  window owned by the gateway-injected user, filtered to
  `stream IN ('me','counterparty')` and `deleted_at IS NULL`.
- The batch-download endpoint streams a `zipfile.ZIP_STORED` archive of
  selected Recordings, gated by ownership / retention / stream-channel
  / size-cap pre-flight checks. Failure modes carry stable `error_code`
  strings the frontend renders via `localizedErrorMessage`.

Pre-flight 4xx mapping:
  - 403 recording.forbidden          — any id not owned by current user
  - 410 recording.retention_expired  — any id soft-deleted or out-of-window
  - 422 recording.invalid_stream     — any id has stream not in (me, counterparty)
  - 413 recording.batch_oversize     — sum of bytes exceeds the configured cap

Implementation choices anchored to design.md:
  - Page-based pagination, default page_size 25, max 100.
  - ILIKE on `meeting.title` (no full-text index).
  - Recording-window membership computed at query time from
    `Settings.recording_retention_days`; no denormalization.
  - ZIP_STORED + StreamingResponse keep peak memory at one read buffer.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.config import Settings, get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.recordings.schemas import (
    BatchDownloadRequest,
    RecordingListResponse,
    RecordingSummary,
)
from meeting_playbook.sessions.models import Recording

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

# 16 kHz mono 16-bit PCM → 32 000 bytes / second. Recording WAVs across the
# capture pipeline use this canonical format (see `audio_playback.range_server`
# + `voice_enrollment` + offline ingest). Duration = (bytes - 44) / byte_rate.
_PCM_BYTES_PER_SECOND = 16_000 * 1 * 2
_WAV_HEADER_BYTES = 44

# Streaming ZIP read buffer. One WAV chunk per write; bounds peak in-flight
# memory regardless of total zip size. 1 MiB picked empirically to amortize
# disk seeks without inflating the working set.
_ZIP_STREAM_CHUNK_BYTES = 1 << 20

_ALLOWED_STREAMS: frozenset[str] = frozenset({"me", "counterparty"})


def _detail(code: str, message: str) -> dict[str, str]:
    return {"error_code": code, "message": message}


def _bytes_to_duration_ms(byte_size: int) -> int:
    """Convert a Recording WAV byte count to milliseconds, header-aware."""
    payload = max(byte_size - _WAV_HEADER_BYTES, 0)
    return (payload * 1000) // _PCM_BYTES_PER_SECOND


_SLUG_NON_ALNUM = re.compile(r"[^A-Za-z0-9_.-]+")


def _slugify(title: str) -> str:
    """Filesystem-safe slug for the per-entry filename inside the zip.

    Keeps ASCII alphanumerics + `_`, `-`, `.`; collapses everything else to
    `-`; strips leading/trailing separators; falls back to `recording` when
    the input title produces an empty result (e.g. CJK-only titles which
    have no ASCII to retain).
    """
    safe = _SLUG_NON_ALNUM.sub("-", title).strip("-_.")
    return safe or "recording"


def _retention_threshold(settings: Settings, now: datetime) -> datetime:
    return now - timedelta(days=settings.recording_retention_days)


@router.get("", response_model=RecordingListResponse)
async def list_recordings(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RecordingListResponse:
    """List the current user's Recordings inside the Recording window.

    Filters compose as `(owner=user) AND (deleted_at IS NULL) AND
    (started_at >= retention_threshold) AND (stream IN allowed)` plus the
    optional `since`/`until`/`search` predicates from query params. The
    response is ordered by `captured_at DESC`.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    retention_floor = _retention_threshold(settings, now)

    conditions = [
        Meeting.user_id == user_id,
        Recording.deleted_at.is_(None),
        Recording.started_at >= retention_floor,
        Recording.stream.in_(_ALLOWED_STREAMS),
    ]

    if since is not None:
        conditions.append(Recording.started_at >= since)
    if until is not None:
        conditions.append(Recording.started_at <= until)
    if search:
        conditions.append(Meeting.title.ilike(f"%{search}%"))

    where_clause = and_(*conditions)

    total = (
        await session.execute(
            select(func.count())
            .select_from(Recording)
            .join(Meeting, Meeting.id == Recording.meeting_id)
            .where(where_clause)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(Recording, Meeting)
            .join(Meeting, Meeting.id == Recording.meeting_id)
            .where(where_clause)
            .order_by(Recording.started_at.desc(), Recording.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    recordings = [
        RecordingSummary(
            id=rec.id,
            meeting_id=rec.meeting_id,
            meeting_title=meeting.title,
            counterparty_label=meeting.counterparty_display_name,
            captured_at=rec.started_at,
            duration_ms=_bytes_to_duration_ms(rec.bytes),
            byte_size=rec.bytes,
            stream=rec.stream,  # type: ignore[arg-type]
        )
        for rec, meeting in rows
    ]

    return RecordingListResponse(
        recordings=recordings,
        total=int(total),
        page=page,
        page_size=page_size,
    )


async def _preflight_and_plan(
    recording_ids: list[str],
    user_id: str,
    session: AsyncSession,
    settings: Settings,
    now: datetime,
) -> tuple[list[tuple[Path, str]], str]:
    """Validate ownership / retention / stream / size and build the zip plan.

    Returns `(plan, archive_name)` on success; raises `HTTPException` with the
    standard `error_code` envelope on the first failure encountered. Shared
    between the JSON preflight endpoint and the GET download endpoint so the
    two stay in lock-step.
    """
    retention_floor = _retention_threshold(settings, now)

    rows = (
        await session.execute(
            select(Recording, Meeting)
            .join(Meeting, Meeting.id == Recording.meeting_id)
            .where(Recording.id.in_(recording_ids))
        )
    ).all()

    found_ids = {rec.id for rec, _ in rows}
    missing = [rid for rid in recording_ids if rid not in found_ids]
    foreign = [rec.id for rec, meeting in rows if meeting.user_id != user_id]
    if missing or foreign:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_detail(
                "recording.forbidden",
                "One or more recordings are not accessible to this user",
            ),
        )

    expired = [
        rec.id for rec, _ in rows if rec.deleted_at is not None or rec.started_at < retention_floor
    ]
    if expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_detail(
                "recording.retention_expired",
                f"{len(expired)} of the selected recordings have passed the Recording window",
            ),
        )

    invalid_stream = [rec.id for rec, _ in rows if rec.stream not in _ALLOWED_STREAMS]
    if invalid_stream:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "recording.invalid_stream",
                "Selected recordings include an unsupported stream channel",
            ),
        )

    total_bytes = sum(rec.bytes for rec, _ in rows)
    cap = settings.recording_batch_download_max_bytes
    if total_bytes > cap:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=_detail(
                "recording.batch_oversize",
                f"Selected recordings exceed the configured size cap of {cap} bytes",
            ),
        )

    plan = [
        (
            Path(rec.file_path),
            f"{_slugify(meeting.title)}_{rec.started_at.strftime('%Y%m%dT%H%M%SZ')}_{rec.stream}.wav",
        )
        for rec, meeting in rows
    ]
    archive_name = f"recordings-{now.strftime('%Y%m%d-%H%M%S')}.zip"
    return plan, archive_name


@router.post("/batch-download/preflight")
async def batch_download_preflight(
    body: BatchDownloadRequest,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, object]:
    """Validate a batch-download request without streaming any bytes.

    The frontend POSTs the selected recording ids here, surfaces any 4xx
    error envelope to the user, then triggers the actual download via a
    direct anchor-click on the GET endpoint so the browser streams the
    zip straight to disk (no JS Blob buffer in memory).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    plan, archive_name = await _preflight_and_plan(
        body.recording_ids, user_id, session, settings, now
    )
    return {
        "ok": True,
        "archive_name": archive_name,
        "entry_count": len(plan),
    }


@router.get("/batch-download")
async def batch_download(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    ids: Annotated[str, Query(min_length=1, max_length=8000)],
) -> StreamingResponse:
    """Stream a ZIP of selected Recordings (ZIP_STORED, per-row WAV).

    `ids` is a comma-separated list of Recording UUIDs (max ~200 entries,
    bounded by `BatchDownloadRequest.recording_ids.max_length`). The GET
    shape lets the browser stream the response directly to disk, avoiding
    the multi-GiB JS Blob a POST + fetch().blob() pattern would require.
    """
    recording_ids = [piece for piece in (chunk.strip() for chunk in ids.split(",")) if piece]
    if not recording_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("recording.invalid_request", "ids query parameter is empty"),
        )
    if len(recording_ids) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "recording.invalid_request",
                "ids query parameter exceeds the 200-entry limit",
            ),
        )

    settings = get_settings()
    now = datetime.now(UTC)
    plan, archive_name = await _preflight_and_plan(recording_ids, user_id, session, settings, now)

    return StreamingResponse(
        _zip_stream(plan),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
    )


class _StreamingBuffer(io.RawIOBase):
    """Backing buffer for `zipfile.ZipFile` that drains via `pop()`.

    `ZipFile` writes synchronously into the file-like we hand it. We
    intercept those writes into an in-memory buffer; the async generator
    drains the buffer between zip operations so peak memory stays bounded
    by `_ZIP_STREAM_CHUNK_BYTES`.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self._buf.extend(b)
        return len(b)

    def pop(self) -> bytes:
        out = bytes(self._buf)
        self._buf.clear()
        return out


async def _zip_stream(
    plan: list[tuple[Path, str]],
) -> AsyncIterator[bytes]:
    """Yield bytes of a ZIP_STORED archive, one WAV chunk at a time."""
    sink = _StreamingBuffer()
    with zipfile.ZipFile(sink, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for wav_path, entry_name in plan:
            if not wav_path.exists():
                logger.warning(
                    "batch_download: file missing for entry %s (%s); skipping",
                    entry_name,
                    wav_path,
                )
                continue
            with (
                zf.open(entry_name, mode="w", force_zip64=True) as entry,
                wav_path.open("rb") as src,
            ):
                while True:
                    chunk = src.read(_ZIP_STREAM_CHUNK_BYTES)
                    if not chunk:
                        break
                    entry.write(chunk)
                    out = sink.pop()
                    if out:
                        yield out
            tail = sink.pop()
            if tail:
                yield tail
    final = sink.pop()
    if final:
        yield final
