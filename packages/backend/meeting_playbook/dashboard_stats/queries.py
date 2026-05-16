"""`DashboardStatsQuery` deep module — read-only aggregates over user's meetings.

Sean revision 3 (slice-18 follow-up): the dashboard switched from a
range-based picker (`this_week / this_month / last_6_months`) to a
month-arrow picker (`YYYY-MM`). The query module now returns:

  - month / prev_month — anchor strings (`YYYY-MM`)
  - meeting_count + prev_month_meeting_count
  - avg_duration_seconds (actual `ended_at - started_at`, completed only)
  - total_duration_seconds (actual, completed only)
  - daily_trend (one entry per day-of-month, zero-filled)
  - hour_distribution (0..23, zero-filled)
  - top_counterparties (up to 5)
  - tag_distribution (S17 placeholder — empty until tag schema lands)

All period math is anchored in `Asia/Taipei`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.dashboard_stats.clock import Clock, SystemClock

TAIPEI = ZoneInfo("Asia/Taipei")


# ─── DTOs ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TopCounterparty:
    display_name: str
    count: int


@dataclass(frozen=True)
class TagBucket:
    tag: str
    count: int


@dataclass(frozen=True)
class DailyBucket:
    day: int  # 1..31, day-of-month
    count: int


@dataclass(frozen=True)
class HourBucket:
    hour: int  # 0..23
    count: int


@dataclass(frozen=True)
class DashboardStats:
    month: str  # YYYY-MM (Asia/Taipei)
    prev_month: str  # YYYY-MM (Asia/Taipei)
    meeting_count: int
    prev_month_meeting_count: int
    avg_duration_seconds: float | None
    total_duration_seconds: float
    top_counterparties: list[TopCounterparty]
    daily_trend: list[DailyBucket] = field(default_factory=list)
    hour_distribution: list[HourBucket] = field(default_factory=list)
    tag_distribution: list[TagBucket] = field(default_factory=list)


# ─── Period boundary helpers ─────────────────────────────────────────────


def _to_taipei(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("month math requires tz-aware datetime")
    return dt.astimezone(TAIPEI)


def _start_of_month(d: datetime) -> datetime:
    d = _to_taipei(d)
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(d: datetime, months: int) -> datetime:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return d.replace(year=year, month=month)


def _month_str(d: datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _parse_month(month: str) -> datetime:
    """Parse `YYYY-MM` into the month-start datetime at Asia/Taipei midnight."""
    try:
        year_str, month_str = month.split("-", 1)
        year = int(year_str)
        month_num = int(month_str)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid month string: {month!r} (expected YYYY-MM)") from None
    if not (1 <= month_num <= 12):
        raise ValueError(f"Invalid month: {month_num} (must be 1..12)")
    if not (1970 <= year <= 9999):
        raise ValueError(f"Invalid year: {year}")
    return datetime(year, month_num, 1, 0, 0, 0, tzinfo=TAIPEI)


def _days_in_month(d: datetime) -> int:
    """Number of days in the calendar month containing `d`."""
    next_month = _add_months(d.replace(day=1), 1)
    return (next_month - d.replace(day=1)).days


# ─── Backward-compat shims (older tests / external callers) ──────────────


ALLOWED_RANGES: frozenset[str] = frozenset({"this_week", "this_month", "last_6_months"})


def compute_period_boundaries(now: datetime, range_: str) -> tuple[datetime, datetime]:
    """Legacy helper kept for backward-compat tests; only `this_month` makes
    sense after the redesign and is preserved for migration safety.
    """
    if range_ != "this_month":
        raise ValueError(
            "compute_period_boundaries is retained only for 'this_month'; use "
            "DashboardStatsQuery.execute(user_id, month=...) instead."
        )
    start = _start_of_month(now)
    return start, _add_months(start, 1)


# ─── Query module ────────────────────────────────────────────────────────


class DashboardStatsQuery:
    """Deep module: aggregates dashboard stats for a single user + month.

    Reads-only. Owns no state besides the injected session + clock.
    """

    def __init__(self, session: AsyncSession, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    async def execute(self, user_id: str, month: str | None = None) -> DashboardStats:
        """Return the dashboard for `user_id` in `month` (default: current month)."""
        if month is None:
            month_start = _start_of_month(self._clock.now())
        else:
            month_start = _parse_month(month)
        month_end = _add_months(month_start, 1)
        prev_month_start = _add_months(month_start, -1)

        # Header: total + actual avg/sum duration + previous-month total.
        result = await self._session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE scheduled_start_at >= :start AND scheduled_start_at < :end
                    ) AS total,
                    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) FILTER (
                        WHERE scheduled_start_at >= :start AND scheduled_start_at < :end
                          AND started_at IS NOT NULL AND ended_at IS NOT NULL
                    ) AS avg_duration,
                    COALESCE(SUM(EXTRACT(EPOCH FROM (ended_at - started_at))) FILTER (
                        WHERE scheduled_start_at >= :start AND scheduled_start_at < :end
                          AND started_at IS NOT NULL AND ended_at IS NOT NULL
                    ), 0) AS total_duration,
                    COUNT(*) FILTER (
                        WHERE scheduled_start_at >= :prev_start AND scheduled_start_at < :start
                    ) AS prev_total
                FROM meeting
                WHERE user_id = :uid
                """
            ),
            {
                "uid": user_id,
                "prev_start": prev_month_start,
                "start": month_start,
                "end": month_end,
            },
        )
        row = result.first()
        total = int(row.total) if row else 0
        avg_duration = float(row.avg_duration) if row and row.avg_duration is not None else None
        total_duration = float(row.total_duration) if row else 0.0
        prev_total = int(row.prev_total) if row else 0

        # Top counterparties — within the month, count DESC tie-broken by name.
        cp_rows = await self._session.execute(
            text(
                """
                SELECT counterparty_display_name AS name, COUNT(*) AS cnt
                FROM meeting
                WHERE user_id = :uid
                  AND scheduled_start_at >= :start
                  AND scheduled_start_at < :end
                  AND counterparty_display_name IS NOT NULL
                  AND counterparty_display_name <> ''
                GROUP BY counterparty_display_name
                """
            ),
            {"uid": user_id, "start": month_start, "end": month_end},
        )
        candidates = [TopCounterparty(display_name=str(r.name), count=int(r.cnt)) for r in cp_rows]
        candidates.sort(key=lambda c: (-c.count, c.display_name))
        top_counterparties = candidates[:5]

        # Daily trend — one entry per day-of-month, zero-filled.
        day_rows = await self._session.execute(
            text(
                """
                SELECT
                    EXTRACT(DAY FROM (scheduled_start_at AT TIME ZONE 'Asia/Taipei'))::int AS day,
                    COUNT(*) AS cnt
                FROM meeting
                WHERE user_id = :uid
                  AND scheduled_start_at >= :start
                  AND scheduled_start_at < :end
                GROUP BY day
                """
            ),
            {"uid": user_id, "start": month_start, "end": month_end},
        )
        counts_by_day = {int(r.day): int(r.cnt) for r in day_rows}
        days = _days_in_month(month_start)
        daily_trend = [
            DailyBucket(day=d, count=counts_by_day.get(d, 0)) for d in range(1, days + 1)
        ]

        # Hour-of-day distribution — 0..23, zero-filled.
        hour_rows = await self._session.execute(
            text(
                """
                SELECT
                    EXTRACT(HOUR FROM (scheduled_start_at AT TIME ZONE 'Asia/Taipei'))::int AS hour,
                    COUNT(*) AS cnt
                FROM meeting
                WHERE user_id = :uid
                  AND scheduled_start_at >= :start
                  AND scheduled_start_at < :end
                GROUP BY hour
                """
            ),
            {"uid": user_id, "start": month_start, "end": month_end},
        )
        counts_by_hour = {int(r.hour): int(r.cnt) for r in hour_rows}
        hour_distribution = [HourBucket(hour=h, count=counts_by_hour.get(h, 0)) for h in range(24)]

        # Tag distribution — counts distinct meetings per tag for the month.
        # `meeting_tag` is the slice-17 join table; `tag.user_id` scopes to
        # the requesting user so we never accidentally surface tags from
        # other users (would be impossible via FK anyway, but explicit).
        tag_rows = await self._session.execute(
            text(
                """
                SELECT t.name AS tag, COUNT(DISTINCT mt.meeting_id) AS cnt
                FROM tag t
                JOIN meeting_tag mt ON mt.tag_id = t.id
                JOIN meeting m ON m.id = mt.meeting_id
                WHERE t.user_id = :uid
                  AND m.user_id = :uid
                  AND m.scheduled_start_at >= :start
                  AND m.scheduled_start_at < :end
                GROUP BY t.name
                ORDER BY cnt DESC, t.name ASC
                """
            ),
            {"uid": user_id, "start": month_start, "end": month_end},
        )
        tag_distribution = [TagBucket(tag=str(r.tag), count=int(r.cnt)) for r in tag_rows]

        return DashboardStats(
            month=_month_str(month_start),
            prev_month=_month_str(prev_month_start),
            meeting_count=total,
            prev_month_meeting_count=prev_total,
            avg_duration_seconds=avg_duration,
            total_duration_seconds=total_duration,
            top_counterparties=top_counterparties,
            daily_trend=daily_trend,
            hour_distribution=hour_distribution,
            tag_distribution=tag_distribution,
        )
