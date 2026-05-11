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

from meeting_playbook.sessions.models import Recording

logger = logging.getLogger(__name__)


async def cleanup(
    *,
    now: datetime,
    retention_days: int,
    recordings_dir: Path,
    session_factory: async_sessionmaker,
) -> int:
    """Sweep `recording` table; unlink old wavs + stamp `deleted_at`.

    Returns the count of rows whose `deleted_at` was stamped this sweep
    (= unlinked-from-disk + self-healed-because-missing).
    """
    threshold = now - timedelta(days=retention_days)
    stamped = 0

    async with session_factory() as session:
        rows = (
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

        for rec in rows:
            wav_path = Path(rec.file_path)
            try:
                wav_path.unlink()
            except FileNotFoundError:
                # Self-heal: file already gone (manual rm, partial prior
                # sweep). Stamp deleted_at so the row's "available" predicate
                # flips false and the next sweep ignores it.
                logger.info(
                    "retention self-heal: %s already missing for recording %s",
                    wav_path,
                    rec.id,
                )
            except OSError as exc:
                # Don't stamp — let the next sweep retry.
                logger.warning(
                    "retention skip %s for recording %s: %s",
                    wav_path,
                    rec.id,
                    exc,
                )
                continue

            rec.deleted_at = now
            stamped += 1

        await session.commit()

    if stamped:
        logger.info("retention sweep: stamped deleted_at on %d recording row(s)", stamped)
    return stamped


__all__ = ["cleanup"]
