"""Clock abstraction for `DashboardStatsQuery` — enables fixed-time tests.

Per slice-18-ia-dashboard Decision 5 (deep module + injected Clock):
- `Clock` is a tiny Protocol that returns "now" as a timezone-aware datetime.
- `SystemClock` is the production implementation (UTC, then converted).
- `FixedClock` returns a fixed instant for tests.

All `DashboardStatsQuery` period math is performed in `Asia/Taipei`
(Decision 2). The Clock returns a UTC `datetime` and the query layer
converts to `Asia/Taipei` when computing buckets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Returns the current instant as a timezone-aware UTC datetime."""

    def now(self) -> datetime: ...


@dataclass(frozen=True)
class SystemClock:
    """Production clock — returns `datetime.now(UTC)`."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class FixedClock:
    """Test clock — always returns the same datetime.

    The fixed datetime MUST be timezone-aware (callers should attach UTC or
    `Asia/Taipei`); we do not coerce a naive datetime because that would hide
    test bugs.
    """

    fixed: datetime

    def now(self) -> datetime:
        if self.fixed.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        return self.fixed
