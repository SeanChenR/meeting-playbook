"""In-flight registry for summary generation tasks (slice-10).

Process-scoped `dict[str, asyncio.Task]` mapping meeting_id to the
in-flight task. Concurrent spawn calls race-protect via `asyncio.Lock`.

Per design.md (slice-10) Decision 3:
- Single source of truth for "is a summary being generated for this
  meeting RIGHT NOW" lives in this module
- POST endpoint checks `is_pending` to gate 409 `summary.busy` responses
- WS finalize block + POST endpoint both go through `spawn_summary_task`
- The spawned task always pops itself from the registry in its finally
  block (regardless of success / failure / cancellation)
- Process restart loses the registry — that's fine; the task dies with
  the process, no row was written, next GET returns 404 → user re-spawns
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.summarization.base import MeetingSummarizer, SummaryFormatError
from meeting_playbook.summarization.repository import SummaryRepository

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)

_inflight: dict[str, asyncio.Task[None]] = {}
_lock = asyncio.Lock()


def is_pending(meeting_id: str) -> bool:
    """True iff a summary task is currently running for the meeting."""
    task = _inflight.get(meeting_id)
    return task is not None and not task.done()


async def _run(
    meeting_id: str,
    summarizer: MeetingSummarizer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Background coroutine: call summarizer, upsert on success, log on failure.

    The `finally` block pops the meeting_id from the registry regardless
    of outcome — success, exception, or cancellation. This guarantees the
    UI's pending → done / not_found transition fires within one GET poll.
    """
    try:
        markdown = await summarizer.summarize(meeting_id)
        async with session_factory() as session:
            await SummaryRepository(session).upsert(meeting_id=meeting_id, markdown=markdown)
        logger.info("summary meeting=%s persisted", meeting_id)
    except asyncio.CancelledError:
        logger.info("summary meeting=%s cancelled", meeting_id)
        raise
    except TimeoutError as exc:
        logger.warning(
            "summary meeting=%s timeout: %s: %s",
            meeting_id,
            type(exc).__name__,
            exc,
        )
    except SummaryFormatError as exc:
        logger.warning("summary meeting=%s format error (no upsert): %s", meeting_id, exc)
    except Exception as exc:
        logger.exception(
            "summary meeting=%s FAILED: %s: %s",
            meeting_id,
            type(exc).__name__,
            exc,
        )
    finally:
        _inflight.pop(meeting_id, None)


async def spawn_summary_task(
    meeting_id: str,
    *,
    summarizer: MeetingSummarizer | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Spawn a background summary task for the meeting.

    Returns True iff a new task was actually created. Returns False when
    a task is already in-flight for the meeting (caller should map to
    HTTP 409 `summary.busy` for the POST path; WS finalize logs at info).

    `summarizer` and `session_factory` are testing seams — production
    callers omit them so the helper resolves them via the FastAPI
    dependency providers.
    """
    if summarizer is None:
        # Lazy import to avoid forcing the dependencies module to load
        # during tests that inject their own summarizer.
        from meeting_playbook.summarization.dependencies import (
            get_meeting_summarizer_dependency,
        )

        summarizer = get_meeting_summarizer_dependency()
    if session_factory is None:
        from meeting_playbook.meetings.dependencies import (
            get_session_factory_dependency,
        )

        session_factory = get_session_factory_dependency()

    async with _lock:
        existing = _inflight.get(meeting_id)
        if existing is not None and not existing.done():
            return False
        task = asyncio.create_task(
            _run(meeting_id, summarizer, session_factory),
            name=f"summary-{meeting_id}",
        )
        _inflight[meeting_id] = task
    return True


__all__ = ["_inflight", "is_pending", "spawn_summary_task"]
