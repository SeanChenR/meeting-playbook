"""Recording retention cleanup — slice-11 task 4.2.

Per slice-11 design Decision 5+6:
- Find every recording row whose `created_at` is older than
  `now - retention_days` AND `deleted_at IS NULL`.
- Try to unlink each wav. If the file is already missing, that's a
  self-heal scenario (manual `rm`, half-finished previous sweep, ...) —
  stamp `deleted_at` anyway so the row's "is the wav available" predicate
  goes false.
- On `OSError` (permission, FS error), log a warning and SKIP that row;
  do NOT stamp `deleted_at`. The next sweep will retry.
- Commit all `deleted_at` updates in one transaction.
- Returns the count of files actually unlinked OR self-healed (rows
  whose `deleted_at` was stamped this sweep).

The cleanup is idempotent: a second run with the same `now` won't touch
any of the rows the first run already processed (their `deleted_at` is
no longer NULL).

Cleanup never touches `transcript_chunk` or `chat_message` rows — only
the `recording` table is in scope.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.attachments.models import MeetingAttachment
from meeting_playbook.sessions.models import Recording

logger = logging.getLogger(__name__)


async def cleanup(
    *,
    now: datetime,
    retention_days: int,
    recordings_dir: Path,
    session_factory: async_sessionmaker,
    attachments_dir: Path | None = None,
) -> int:
    """Sweep `recording` + `meeting_attachment` tables; unlink expired files
    and stamp `deleted_at`.

    Slice-20a expanded the original recording-only sweep to also cover the
    `meeting_attachment` table:
      1. Recording rows older than `retention_days` get their WAV unlinked
         and `deleted_at` stamped.
      2. MeetingAttachment rows older than `retention_days` get their
         backing file unlinked and `deleted_at` stamped.
      3. Both updates commit in a single transaction.

    Returns the total count of rows whose `deleted_at` was stamped this
    sweep (recording + attachment combined). The function is idempotent:
    a second call with the same `now` produces zero new stamps.

    `attachments_dir` is accepted for parity with `recordings_dir` (both
    are passed to the function so future hardening can use them, e.g.
    cross-checking that the file_path lives under the configured root)
    but is not strictly required for the sweep — file_path columns carry
    absolute paths.
    """
    _ = attachments_dir  # reserved for future containment check
    threshold = now - timedelta(days=retention_days)
    stamped = 0

    async with session_factory() as session:
        # ── Recording sweep (existing behaviour) ──────────────────────
        recording_rows = (
            (
                await session.execute(
                    select(Recording).where(
                        Recording.created_at < threshold,
                        Recording.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        for rec in recording_rows:
            wav_path = Path(rec.file_path)
            try:
                wav_path.unlink()
            except FileNotFoundError:
                logger.info(
                    "retention self-heal: %s already missing for recording %s",
                    wav_path,
                    rec.id,
                )
            except OSError as exc:
                logger.warning(
                    "retention skip %s for recording %s: %s",
                    wav_path,
                    rec.id,
                    exc,
                )
                continue

            rec.deleted_at = now
            stamped += 1

        # ── MeetingAttachment sweep (slice-20a addition) ──────────────
        attachment_rows = (
            (
                await session.execute(
                    select(MeetingAttachment).where(
                        MeetingAttachment.uploaded_at < threshold,
                        MeetingAttachment.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        for att in attachment_rows:
            file_path = Path(att.file_path)
            try:
                file_path.unlink()
            except FileNotFoundError:
                logger.info(
                    "retention self-heal: %s already missing for attachment %s",
                    file_path,
                    att.id,
                )
            except OSError as exc:
                logger.warning(
                    "retention skip %s for attachment %s: %s",
                    file_path,
                    att.id,
                    exc,
                )
                continue

            att.deleted_at = now
            stamped += 1

        await session.commit()

    if stamped:
        logger.info("retention sweep: stamped deleted_at on %d row(s)", stamped)
    return stamped


__all__ = ["cleanup"]
