## ADDED Requirements

### Requirement: GET /api/meetings/stats SHALL return aggregated meeting statistics for the authenticated user filtered by range

The backend SHALL expose `GET /api/meetings/stats?range={this_week|this_month|last_6_months}` returning a JSON envelope with `range`, `meeting_count`, `avg_duration_seconds`, `in_progress_count`, `top_counterparty`, `top_counterparties` (up to 5), `tag_distribution`, and `monthly_trend`. The endpoint MUST scope all aggregates to the authenticated user (`X-User-Id` injected by the Bun gateway). When `range` is omitted, the endpoint SHALL default to `this_month`. When `range` is any value not in the whitelist, the endpoint SHALL return HTTP 400 with `{"error_code": "stats.invalid_range", "message": ...}`.

#### Scenario: this_month returns counts and trend for current month

- **WHEN** the authenticated user calls `GET /api/meetings/stats?range=this_month`
- **THEN** the response contains `meeting_count`, `avg_duration_seconds`, `in_progress_count`, `top_counterparty`, `top_counterparties`, `tag_distribution`, and a `monthly_trend` array with exactly one entry whose `month` matches the current month in `Asia/Taipei`

##### Example: this_month with three meetings

- **GIVEN** authenticated user has three meetings in current Asia/Taipei month with durations 1800s, 2700s, 3600s; one meeting `status = in_progress`
- **WHEN** the user calls `GET /api/meetings/stats?range=this_month`
- **THEN** response is `{"range": "this_month", "meeting_count": 3, "avg_duration_seconds": 2700.0, "in_progress_count": 1, "top_counterparty": {...}, "top_counterparties": [...], "tag_distribution": [...], "monthly_trend": [{"month": "<current YYYY-MM>", "count": 3}]}`

#### Scenario: invalid range returns 400

- **WHEN** the authenticated user calls `GET /api/meetings/stats?range=last_year`
- **THEN** the response status is 400 and the body is `{"error_code": "stats.invalid_range", "message": ...}`

#### Scenario: missing range defaults to this_month

- **WHEN** the authenticated user calls `GET /api/meetings/stats` with no `range` parameter
- **THEN** the response `range` field equals `"this_month"` and aggregates correspond to the current Asia/Taipei month

### Requirement: DashboardStatsQuery SHALL compute period boundaries in Asia/Taipei

The `DashboardStatsQuery` deep module MUST compute all period boundaries in `Asia/Taipei` regardless of how meeting timestamps are stored. Bucket comparisons MUST use the half-open interval `[start, end)`. The module MUST accept a `Clock` dependency to allow fixed-time testing.

#### Scenario: this_week starts Monday at 00:00 Asia/Taipei

- **WHEN** the current time is Thursday 14:00 Asia/Taipei
- **THEN** `DashboardStatsQuery` computes the `this_week` range as `[Monday 00:00 Asia/Taipei, next Monday 00:00 Asia/Taipei)`

##### Example: boundary cases for period start and end

| Range            | Now (Asia/Taipei)          | Start (inclusive)            | End (exclusive)             | monthly_trend buckets |
| ---------------- | -------------------------- | ---------------------------- | --------------------------- | --------------------- |
| `this_week`      | 2026-05-15 14:00 (Friday)  | 2026-05-11 00:00 (Mon)        | 2026-05-18 00:00 (Mon)       | 1                     |
| `this_month`     | 2026-05-15 14:00            | 2026-05-01 00:00              | 2026-06-01 00:00             | 1                     |
| `last_6_months`  | 2026-05-15 14:00            | 2025-12-01 00:00              | 2026-06-01 00:00             | 6                     |
| `this_month`     | 2026-01-01 00:30            | 2026-01-01 00:00              | 2026-02-01 00:00             | 1                     |
| `last_6_months`  | 2026-01-15 14:00            | 2025-08-01 00:00              | 2026-02-01 00:00             | 6                     |

#### Scenario: last_6_months always returns 6 buckets including zero-count months

- **WHEN** the current Asia/Taipei time falls in 2026-05 and there are no meetings in 2025-12, 2026-02
- **THEN** `monthly_trend` contains 6 entries with `month` values `2025-12, 2026-01, 2026-02, 2026-03, 2026-04, 2026-05` in ascending order; zero-count months have `count: 0`

#### Scenario: meeting at exact period start belongs to that period

- **WHEN** a meeting's `scheduled_start_at` equals the period start (e.g., 2026-05-01 00:00 Asia/Taipei for `this_month`)
- **THEN** the meeting is included in that period's aggregates

#### Scenario: meeting at exact period end belongs to the next period

- **WHEN** a meeting's `scheduled_start_at` equals the period end (e.g., 2026-06-01 00:00 Asia/Taipei for the 2026-05 `this_month` period)
- **THEN** the meeting is excluded from the `this_month` aggregates because the interval is half-open

### Requirement: Top counterparty ranking SHALL use deterministic tie-breakers

`top_counterparty` and `top_counterparties` MUST rank entries by `count DESC`, then by `display_name` in zh-TW locale-aware ascending order, then by raw `display_name` codepoint ascending as a deterministic fallback. Entries whose `counterparty_display_name` is NULL or empty MUST be excluded. `top_counterparties` MUST return at most 5 entries. If no qualifying meetings exist, `top_counterparty` SHALL be `null` and `top_counterparties` SHALL be an empty array.

#### Scenario: equal counts ordered alphabetically

- **WHEN** counterparties `Acme Corp` and `Initech` each have count 3 in the current period
- **THEN** `top_counterparties[0].display_name == "Acme Corp"` and `top_counterparties[1].display_name == "Initech"`

##### Example: ranking with ties and exclusions

| Input (display_name, count)                                | top_counterparty       | top_counterparties (order)                |
| ---------------------------------------------------------- | ---------------------- | ----------------------------------------- |
| Acme=4, Initech=3, Soylent=3, NULL=2, ""=1                 | Acme (count=4)         | Acme, Initech, Soylent                    |
| Acme=2, Beta=2, Cyber=2, Delta=2, Echo=2, Foxtrot=2         | Acme (count=2)         | Acme, Beta, Cyber, Delta, Echo (top 5)    |
| (none — all NULL)                                          | null                   | []                                        |

### Requirement: Dashboard page SHALL render four charts and a period switcher

The `/dashboard` route SHALL render four chart regions powered by `GET /api/meetings/stats`: a stat card cluster (meeting count, avg duration, in-progress count, top counterparty), a top counterparties bar chart, a tag distribution donut, and a 6-month monthly trend line. A period switcher control MUST allow the user to toggle between `this_week`, `this_month`, and `last_6_months`. The default selected period MUST be `this_month`. Switching the period MUST trigger a re-fetch and re-render of all four regions.

#### Scenario: period switcher refetches stats

- **WHEN** the user clicks the period switcher and selects `last_6_months`
- **THEN** the page issues `GET /api/meetings/stats?range=last_6_months` and updates all four regions with the new data

#### Scenario: empty state when no meetings in period

- **WHEN** the response contains `meeting_count: 0`
- **THEN** each of the four regions renders its own empty state copy (translated through `dashboard.*` i18n keys) and chart areas show no data placeholders

#### Scenario: chart colors follow theme

- **WHEN** the user switches between light theme (purple primary) and dark theme (warm orange primary)
- **THEN** the chart primary series color reads from `var(--primary)` and adapts without page reload

### Requirement: Stats endpoint response SHALL conform to a stable JSON schema

The response body MUST contain the fields and types defined below. Field ordering is not guaranteed to be stable across responses, but field presence is required. All numeric counts MUST be non-negative integers. `avg_duration_seconds` MUST be a non-negative number or `null` (when `meeting_count` is 0).

#### Scenario: response shape

- **WHEN** the endpoint returns 200
- **THEN** the body matches:

##### Example: response field contract

| Field                  | Type                                          | Nullability                      | Notes                                                  |
| ---------------------- | --------------------------------------------- | -------------------------------- | ------------------------------------------------------ |
| `range`                | string enum                                   | required                         | `this_week` / `this_month` / `last_6_months`           |
| `meeting_count`        | integer                                       | required                         | non-negative                                           |
| `avg_duration_seconds` | number                                        | nullable                         | null when `meeting_count == 0`                         |
| `in_progress_count`    | integer                                       | required                         | non-negative                                           |
| `top_counterparty`     | `{display_name: string, count: integer}`      | nullable                         | null when no qualifying meeting                        |
| `top_counterparties`   | array of `{display_name, count}`              | required (permitted to be empty) | length ≤ 5                                             |
| `tag_distribution`     | array of `{tag: string, count: integer}`      | required (permitted to be empty) | only tags with `count > 0`                             |
| `monthly_trend`        | array of `{month: "YYYY-MM", count: integer}` | required, length 1 or 6           | length 1 for `this_week`/`this_month`, 6 for `last_6_months` |
