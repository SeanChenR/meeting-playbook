## ADDED Requirements

### Requirement: Meeting list endpoint SHALL support filters and ordering required by the home page regions

`GET /api/meetings` MUST accept the following query parameters in addition to existing ones: `scheduled_date=YYYY-MM-DD` (filter by Asia/Taipei calendar date of `scheduled_start_at`), `status=in_progress` (filter by meeting status), `pending=true` (filter to meetings that have an uploaded recording awaiting ingest OR are completed but lack a summary), `order=scheduled_start_at:asc` and `order=updated_at:desc` (sort by the corresponding field), and `limit=<integer>` (cap the result set size). All filters MUST scope to the authenticated user.

#### Scenario: scheduled_date filter returns today's meetings sorted ascending

- **WHEN** the user calls `GET /api/meetings?scheduled_date=2026-05-15&order=scheduled_start_at:asc`
- **THEN** the response contains only meetings whose `scheduled_start_at` falls on 2026-05-15 in Asia/Taipei, sorted by `scheduled_start_at` ascending

#### Scenario: status=in_progress filter returns active recordings

- **WHEN** the user calls `GET /api/meetings?status=in_progress`
- **THEN** the response contains only meetings with `status == "in_progress"` scoped to the authenticated user

#### Scenario: pending=true filter combines ingest-pending and summary-pending

- **WHEN** the user calls `GET /api/meetings?pending=true`
- **THEN** the response contains meetings that either have an uploaded recording in ingest-pending state OR have `status == "completed"` with no associated summary

#### Scenario: limit caps the result set

- **WHEN** the user calls `GET /api/meetings?order=updated_at:desc&limit=3`
- **THEN** the response contains at most 3 meetings ordered by `updated_at` descending

### Requirement: DashboardStatsQuery deep module SHALL provide read-only aggregates over user's meetings

The backend MUST expose a `DashboardStatsQuery` class in `packages/backend/app/queries/dashboard_stats.py` that depends on an injected `AsyncSession` and `Clock`. The query MUST compute `meeting_count`, `avg_duration_seconds`, `in_progress_count`, `top_counterparty`, `top_counterparties`, `tag_distribution`, and `monthly_trend` for a given user and range. The query MUST NOT mutate any persistent state. The query MUST handle the empty-result case without raising, returning zero counts, `null` averages, `null` top counterparty, and empty arrays for distributions; for `last_6_months` the `monthly_trend` array MUST still contain 6 zero-count entries.

#### Scenario: empty meeting set returns zeroed stats

- **WHEN** `DashboardStatsQuery.execute(user_id, "this_month")` is called for a user with no meetings
- **THEN** the result is `DashboardStats(range="this_month", meeting_count=0, avg_duration_seconds=None, in_progress_count=0, top_counterparty=None, top_counterparties=[], tag_distribution=[], monthly_trend=[{month: "<current YYYY-MM>", count: 0}])`

#### Scenario: tag distribution only includes tags with positive count

- **WHEN** the user has meetings tagged `sales` (3 occurrences), `discovery` (1 occurrence), and no other tag occurrences in the period
- **THEN** `tag_distribution` is `[{"tag": "sales", "count": 3}, {"tag": "discovery", "count": 1}]` in `count DESC, tag ASC` order, with no zero-count entries

##### Example: monthly_trend bucket completeness

| Range            | Buckets returned                                           | Zero-fill behavior                       |
| ---------------- | ---------------------------------------------------------- | ---------------------------------------- |
| `this_week`      | 1 bucket keyed to current Asia/Taipei month (`YYYY-MM`)    | `count: 0` when no meetings              |
| `this_month`     | 1 bucket keyed to current Asia/Taipei month                | `count: 0` when no meetings              |
| `last_6_months`  | 6 buckets, ascending, current month and 5 prior months     | every missing month emitted with `count: 0` |
