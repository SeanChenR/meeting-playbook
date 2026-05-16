"""`GET /api/meetings/stats` FastAPI router (Sean revision 3).

Endpoint shape:
    GET /api/meetings/stats?month=YYYY-MM

- `month` default: current month in Asia/Taipei.
- Invalid `month` (bad format or out-of-range): HTTP 400 with
  `{"error_code": "stats.invalid_range", ...}` (stable code preserved
  from the previous range-based contract).
- Auth: gateway-injected `X-User-Id` header.

The clock is injected via FastAPI dependency so tests can pin a fixed instant.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.dashboard_stats.clock import Clock, SystemClock
from meeting_playbook.dashboard_stats.queries import DashboardStatsQuery
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)

router = APIRouter(prefix="/api/meetings", tags=["dashboard-stats"])


def get_clock_dependency() -> Clock:
    """Return the request-scoped Clock; tests override with `FixedClock`."""
    return SystemClock()


@router.get("/stats")
async def get_stats(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    clock: Annotated[Clock, Depends(get_clock_dependency)],
    month: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    try:
        stats = await DashboardStatsQuery(session, clock=clock).execute(
            user_id=user_id, month=month
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "stats.invalid_range",
                "message": str(exc),
            },
        ) from exc

    return {
        "month": stats.month,
        "prev_month": stats.prev_month,
        "meeting_count": stats.meeting_count,
        "prev_month_meeting_count": stats.prev_month_meeting_count,
        "avg_duration_seconds": stats.avg_duration_seconds,
        "total_duration_seconds": stats.total_duration_seconds,
        "top_counterparties": [
            {"display_name": tc.display_name, "count": tc.count} for tc in stats.top_counterparties
        ],
        "daily_trend": [{"day": d.day, "count": d.count} for d in stats.daily_trend],
        "hour_distribution": [{"hour": h.hour, "count": h.count} for h in stats.hour_distribution],
        "tag_distribution": [{"tag": tb.tag, "count": tb.count} for tb in stats.tag_distribution],
    }
