"""MeetingExportBundler — assembles a per-meeting ZIP bundle as a byte stream.

Per slice-22-export-bundle design.md:

  Decision "Python stdlib zipfile + FastAPI StreamingResponse, 不引第三方 streaming ZIP":
    we wrap a `tempfile.SpooledTemporaryFile(max_size=4 MiB)` in
    `zipfile.ZipFile(..., allowZip64=True)`. Small bundles stay entirely in
    memory; only the rare large-WAV case spills to disk.

  Decision "串流推送策略：write_iter pattern with chunked WAV stdin":
    every Recording WAV is written into its ZIP entry via
    `chunked_wav_reader(path, EXPORT_WAV_CHUNK_BYTES=1 MiB)`. Generators
    drain the spool every chunk so heap pressure stays bounded.

  Decision "Recording 過期判斷下推到 SQL":
    the recording query filters `deleted_at IS NULL` at the database
    layer — no `Path.exists()` second check. Slice-11 cleanup guarantees
    the invariant.

  Decision "跨用戶授權與既有 Meeting ownership 一致":
    we delegate ownership to `MeetingRepository.get_for_user`. A miss
    raises `MeetingNotFound`, which the router maps to HTTP 404
    `meeting.not_found`.

  Decision "1 MiB chunk 寫死成常數":
    `EXPORT_WAV_CHUNK_BYTES = 1 << 20`. Not exposed as an env var.

S20a integration note (slice-20a-meeting-attachment is parked in another
worktree and not yet on main): the design.md for slice-22 deliberately
omits attachments. We expose `_iter_attachment_entries` as a stub hook so
when S20a lands, integration becomes a one-function change without forcing
slice-22 to depend on S20a's schema. Until then it is a no-op that yields
nothing — preserving the bundler's import-time safety on a clean main
without the `attachment` table.
"""

from __future__ import annotations

import tempfile
import zipfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.export.markdown import (
    playbook_to_markdown,
    summary_to_markdown,
    transcript_to_markdown,
)
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.playbooks.models import Playbook
from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.summarization.models import Summary

EXPORT_WAV_CHUNK_BYTES = 1 << 20  # 1 MiB
_SPOOL_MAX_SIZE = 4 * 1024 * 1024  # 4 MiB — spool stays in RAM until this
_DRAIN_CHUNK_BYTES = 1 << 20  # 1 MiB drain step from spool to client


class MeetingNotFound(Exception):
    """Raised when the meeting does not exist OR is owned by a different user.

    The router maps this to HTTP 404 with `error_code = meeting.not_found`
    so the response never leaks the "missing vs not-owned" distinction.
    """


def chunked_wav_reader(path: Path, chunk_bytes: int = EXPORT_WAV_CHUNK_BYTES) -> Iterator[bytes]:
    """Yield WAV file bytes in fixed-size chunks.

    `path.open("rb")` plus a walrus loop is the streaming idiom from design
    decision "串流推送策略": the bundler MUST NOT call `f.read()` on the
    whole file (a 50–100 MiB dual-channel meeting would blow the FastAPI
    worker's heap).
    """
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_bytes)
            if not chunk:
                break
            yield chunk


class MeetingExportBundler:
    """Deep module — assembles and streams the per-meeting ZIP bundle.

    Public surface is a single async generator method
    `iter_zip_chunks(meeting_id, user_id)`. Internal helpers handle DB
    queries, markdown serialization, and the spool/drain dance.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def iter_zip_chunks(self, *, meeting_id: str, user_id: str) -> AsyncIterator[bytes]:
        """Yield ZIP archive bytes incrementally for an owned meeting.

        Algorithm:
          1. Load meeting + child rows under a request-scoped AsyncSession.
             Cross-user / missing → raise MeetingNotFound BEFORE opening
             the spool, so no I/O is wasted.
          2. Open a SpooledTemporaryFile (4 MiB threshold). Wrap with
             zipfile.ZipFile(..., allowZip64=True). The spool is kept
             monotonic — we never seek/truncate underneath ZipFile because
             ZipFile records absolute offsets internally and rewinding
             corrupts the central directory.
          3. Write all entries (markdown small, recordings streamed via
             chunked WAV reader); after every chunk-write, snapshot
             the spool's growth and yield those bytes to the client so
             the response streams progressively rather than ballooning
             past the spool's RAM threshold.
          4. Close the ZipFile (writes central directory) and yield the
             remaining tail.
        """
        meeting, playbook, chunks, summary, recordings = await self._load(
            meeting_id=meeting_id, user_id=user_id
        )

        with tempfile.SpooledTemporaryFile(max_size=_SPOOL_MAX_SIZE) as spool:
            archive = zipfile.ZipFile(spool, mode="w", allowZip64=True)
            cursor = 0  # bytes already yielded to client
            try:
                # --- Markdown entries ----------------------------------
                archive.writestr(
                    "playbook.md",
                    playbook_to_markdown(playbook, meeting_title=meeting.title),
                )
                archive.writestr("transcript.md", transcript_to_markdown(chunks))
                if summary is not None:
                    archive.writestr("summary.md", summary_to_markdown(summary))

                # --- Attachment entries (S20a hook) --------------------
                # No-op until slice-20a lands. See module docstring.
                for arcname, content in self._iter_attachment_entries(meeting_id=meeting_id):
                    archive.writestr(arcname, content)

                # Stream what we have so far (markdown is small but we
                # still drain to keep latency low for the first byte).
                async for buf in self._yield_pending(spool, cursor):
                    cursor += len(buf)
                    yield buf

                # --- Recording entries — chunked write_iter ------------
                for rec in recordings:
                    arcname = f"recordings/{rec.stream}.wav"
                    rec_path = Path(rec.file_path)
                    with archive.open(arcname, mode="w", force_zip64=True) as entry:
                        for wav_chunk in chunked_wav_reader(rec_path):
                            entry.write(wav_chunk)
                            # Drain after each WAV chunk so memory stays
                            # bounded — the read cursor advances past the
                            # bytes we just emitted, but the spool tail
                            # only grows by O(chunk_bytes) before being
                            # drained on the next iteration.
                            async for buf in self._yield_pending(spool, cursor):
                                cursor += len(buf)
                                yield buf
                    async for buf in self._yield_pending(spool, cursor):
                        cursor += len(buf)
                        yield buf
            finally:
                archive.close()
            # Central directory just landed in the spool — flush the tail.
            async for buf in self._yield_pending(spool, cursor):
                cursor += len(buf)
                yield buf

    async def _load(
        self, *, meeting_id: str, user_id: str
    ) -> tuple[
        Meeting,
        Playbook,
        list[TranscriptChunk],
        Summary | None,
        list[Recording],
    ]:
        """Single round-trip per table; raises MeetingNotFound on miss."""
        async with self._session_factory() as session:
            meeting_repo = MeetingRepository(session)
            meeting = await meeting_repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
            if meeting is None:
                raise MeetingNotFound(meeting_id)

            playbook_result = await session.execute(
                select(Playbook).where(Playbook.meeting_id == meeting_id)
            )
            playbook = playbook_result.scalar_one_or_none()
            # Empty Playbook is still a valid bundle (spec: "Meeting with
            # empty Playbook content still writes playbook.md"). Build a
            # transient empty Playbook so the markdown serializer always
            # has the seven attributes it expects.
            if playbook is None:
                playbook = Playbook(
                    id="",
                    meeting_id=meeting_id,
                    free_form_markdown="",
                    objective="",
                    counterparty_profile="",
                    anticipated_topics="",
                    anticipated_objections="",
                    talking_points="",
                    red_lines="",
                    created_at=meeting.created_at,
                    updated_at=meeting.created_at,
                )

            chunks_result = await session.execute(
                select(TranscriptChunk)
                .where(TranscriptChunk.meeting_id == meeting_id)
                .order_by(TranscriptChunk.started_at.asc())
            )
            chunks = list(chunks_result.scalars().all())

            summary_result = await session.execute(
                select(Summary).where(Summary.meeting_id == meeting_id)
            )
            summary = summary_result.scalar_one_or_none()

            # Recording filter is the contract from spec
            # "Export bundle MUST exclude recordings whose Recording row
            # is soft-deleted" — `deleted_at IS NULL` at the SQL layer.
            recordings_result = await session.execute(
                select(Recording)
                .where(
                    Recording.meeting_id == meeting_id,
                    Recording.deleted_at.is_(None),
                )
                .order_by(Recording.stream.asc())
            )
            recordings = list(recordings_result.scalars().all())

            return meeting, playbook, chunks, summary, recordings

    def _iter_attachment_entries(self, *, meeting_id: str) -> Iterator[tuple[str, bytes]]:
        """Hook for slice-20a attachment integration. No-op until S20a lands.

        Yields `(arcname, content_bytes)` pairs to be written into the ZIP
        under e.g. `attachments/<filename>`. Returning an empty iterator
        keeps the bundle shape exactly as the slice-22 spec defines while
        S20a is still in another worktree.

        When slice-20a lands, this implementation will query the
        `meeting_attachment` table (filter `deleted_at IS NULL`) and stream
        each attachment's file_path content into the ZIP.
        """
        # Intentionally empty for slice-22. Marker for slice-20a integration:
        # `_meeting_id_unused` keeps the meeting_id available without
        # tripping ruff's unused-parameter rule once the body is filled in.
        del meeting_id
        return iter(())

    async def _yield_pending(
        self, spool: tempfile.SpooledTemporaryFile, cursor: int
    ) -> AsyncIterator[bytes]:
        """Yield bytes the spool has accumulated past `cursor`.

        The spool is monotonic — ZipFile writes at the tail and records
        absolute offsets we MUST NOT disturb. We only read forward from
        `cursor` to the current tail. Memory stays bounded as long as the
        caller drains soon after each write (1 MiB granularity here).

        We deliberately do NOT truncate the spool; on a 200 MiB WAV we
        rely on `_SPOOL_MAX_SIZE = 4 MiB` causing the spool to spill to
        disk transparently — the underlying tempfile rotates from RAM to
        an on-disk file once it crosses the threshold, and Python's heap
        footprint stays at O(chunk_bytes).
        """
        tail = spool.tell()
        if tail <= cursor:
            return
        spool.seek(cursor)
        try:
            remaining = tail - cursor
            while remaining > 0:
                chunk = spool.read(min(_DRAIN_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            # Restore the spool's write position so ZipFile's next write
            # lands at the tail, not at our read cursor.
            spool.seek(tail)


__all__ = [
    "EXPORT_WAV_CHUNK_BYTES",
    "MeetingExportBundler",
    "MeetingNotFound",
    "chunked_wav_reader",
]
