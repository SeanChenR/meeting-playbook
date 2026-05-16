"""DashboardStatsQuery tests — Sean revision 3 (month-based picker).

Covers the new public surface:
  - meeting_count + prev_month_meeting_count for arrow-key comparison
  - avg_duration_seconds + total_duration_seconds (actual durations)
  - daily_trend (zero-filled day-of-month buckets)
  - hour_distribution (0..23 zero-filled buckets)
  - top_counterparties (max 5, deterministic tie-break)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.dashboard_stats.clock import FixedClock
from meeting_playbook.dashboard_stats.queries import DashboardStatsQuery

# 2026-05-15 14:00 UTC == 2026-05-15 22:00 Asia/Taipei.
_NOW = datetime(2026, 5, 15, 14, 0, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def seeded_session(migrated_engine):
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_d', 'Sean', 'sean@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await s.commit()
        yield s


def _dt(iso: str | None) -> datetime | None:
    if iso is None:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


async def _insert_meeting(
    s,
    *,
    mid: str,
    start_iso: str,
    end_iso: str | None = None,
    actual_start: str | None = None,
    actual_end: str | None = None,
    counterparty: str = "Acme",
) -> None:
    await s.execute(
        text(
            """
            INSERT INTO meeting (
              id, user_id, title,
              counterparty_display_name, me_display_name,
              scheduled_start_at, scheduled_end_at,
              started_at, ended_at
            )
            VALUES (
              :mid, 'u_d', :title,
              :cp, 'Sean',
              :start, :end,
              :a_start, :a_end
            )
            """
        ),
        {
            "mid": mid,
            "title": f"Meeting {mid}",
            "cp": counterparty,
            "start": _dt(start_iso),
            "end": _dt(end_iso),
            "a_start": _dt(actual_start),
            "a_end": _dt(actual_end),
        },
    )
    await s.commit()


@pytest.mark.asyncio
async def test_meeting_count_and_prev_month_count(seeded_session):
    # 2 meetings in May 2026, 1 meeting in April 2026.
    await _insert_meeting(seeded_session, mid="m1", start_iso="2026-05-05T03:00:00Z")
    await _insert_meeting(seeded_session, mid="m2", start_iso="2026-05-12T08:00:00Z")
    await _insert_meeting(seeded_session, mid="m3", start_iso="2026-04-20T03:00:00Z")
    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))

    stats = await query.execute("u_d", "2026-05")
    assert stats.month == "2026-05"
    assert stats.prev_month == "2026-04"
    assert stats.meeting_count == 2
    assert stats.prev_month_meeting_count == 1


@pytest.mark.asyncio
async def test_avg_and_total_duration_use_actual_timestamps(seeded_session):
    # 45-min actual + 15-min actual + 1 scheduled-only (excluded).
    await _insert_meeting(
        seeded_session,
        mid="m1",
        start_iso="2026-05-05T03:00:00Z",
        actual_start="2026-05-05T03:00:00Z",
        actual_end="2026-05-05T03:45:00Z",
    )
    await _insert_meeting(
        seeded_session,
        mid="m2",
        start_iso="2026-05-06T03:00:00Z",
        actual_start="2026-05-06T03:00:00Z",
        actual_end="2026-05-06T03:15:00Z",
    )
    await _insert_meeting(seeded_session, mid="m3", start_iso="2026-05-07T03:00:00Z")

    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    stats = await query.execute("u_d", "2026-05")
    # avg = (2700 + 900) / 2 = 1800s
    assert stats.avg_duration_seconds == pytest.approx(1800.0)
    # total = 2700 + 900 = 3600s
    assert stats.total_duration_seconds == pytest.approx(3600.0)


@pytest.mark.asyncio
async def test_daily_trend_is_zero_filled_and_indexed_by_day_of_month(seeded_session):
    await _insert_meeting(seeded_session, mid="m1", start_iso="2026-05-05T03:00:00Z")
    await _insert_meeting(seeded_session, mid="m2", start_iso="2026-05-05T09:00:00Z")
    await _insert_meeting(seeded_session, mid="m3", start_iso="2026-05-20T03:00:00Z")

    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    stats = await query.execute("u_d", "2026-05")
    assert len(stats.daily_trend) == 31  # May has 31 days
    by_day = {b.day: b.count for b in stats.daily_trend}
    assert by_day[5] == 2
    assert by_day[20] == 1
    # Every other day is zero-filled
    assert by_day[1] == 0
    assert by_day[31] == 0


@pytest.mark.asyncio
async def test_hour_distribution_is_24_buckets_zero_filled(seeded_session):
    # 03:00 UTC == 11:00 Taipei; 06:00 UTC == 14:00 Taipei.
    await _insert_meeting(seeded_session, mid="m1", start_iso="2026-05-05T03:00:00Z")
    await _insert_meeting(seeded_session, mid="m2", start_iso="2026-05-06T06:00:00Z")

    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    stats = await query.execute("u_d", "2026-05")
    assert len(stats.hour_distribution) == 24
    by_hour = {b.hour: b.count for b in stats.hour_distribution}
    assert by_hour[11] == 1
    assert by_hour[14] == 1
    assert by_hour[0] == 0
    assert by_hour[23] == 0


@pytest.mark.asyncio
async def test_top_counterparties_within_month_only(seeded_session):
    await _insert_meeting(
        seeded_session, mid="m1", start_iso="2026-05-05T03:00:00Z", counterparty="Acme"
    )
    await _insert_meeting(
        seeded_session, mid="m2", start_iso="2026-05-06T03:00:00Z", counterparty="Acme"
    )
    await _insert_meeting(
        seeded_session, mid="m3", start_iso="2026-05-07T03:00:00Z", counterparty="Initech"
    )
    # April Acme is excluded
    await _insert_meeting(
        seeded_session, mid="m4", start_iso="2026-04-05T03:00:00Z", counterparty="Acme"
    )

    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    stats = await query.execute("u_d", "2026-05")
    assert [tc.display_name for tc in stats.top_counterparties] == ["Acme", "Initech"]
    assert stats.top_counterparties[0].count == 2
    assert stats.top_counterparties[1].count == 1


@pytest.mark.asyncio
async def test_default_month_uses_clock(seeded_session):
    await _insert_meeting(seeded_session, mid="m1", start_iso="2026-05-05T03:00:00Z")
    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    stats = await query.execute("u_d")  # month omitted
    assert stats.month == "2026-05"


@pytest.mark.asyncio
async def test_invalid_month_format_raises(seeded_session):
    query = DashboardStatsQuery(seeded_session, clock=FixedClock(_NOW))
    with pytest.raises(ValueError):
        await query.execute("u_d", "2026-13")
    with pytest.raises(ValueError):
        await query.execute("u_d", "not-a-month")
