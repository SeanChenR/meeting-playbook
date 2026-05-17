"""Recording retention background loop — slice-11 task 4.3.

Per slice-11 design Decision 6:
- One `cleanup` call at app startup (immediate sweep so the user doesn't
  wait 24h for the first cleanup to fire after a long-running deploy).
- Then `await asyncio.sleep(24 * 3600)` between subsequent sweeps.
- Any exception from a single iteration is logged via `logger.exception`
  and swallowed; the loop SHALL keep running.
- `asyncio.CancelledError` is re-raised so FastAPI's lifespan finalizer
  can shut the task down cleanly during app teardown.

`run_forever` is wired in by `server.py`'s `lifespan` context manager.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.config import Settings
from meeting_playbook.retention.job import cleanup

logger = logging.getLogger(__name__)

_DAY_IN_SECONDS = 24 * 3600


async def run_forever(
    *,
    settings: Settings,
    session_factory: async_sessionmaker,
) -> None:
    """Infinite cleanup loop. Cancellable; CancelledError re-raises cleanly."""
    while True:
        try:
            await cleanup(
                now=datetime.now(UTC),
                retention_days=settings.recording_retention_days,
                recordings_dir=Path(settings.recordings_dir).expanduser(),
                attachments_dir=Path(settings.attachment_dir).expanduser(),
                session_factory=session_factory,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("retention sweep failed; will retry on next cycle")
        await asyncio.sleep(_DAY_IN_SECONDS)


__all__ = ["run_forever"]
