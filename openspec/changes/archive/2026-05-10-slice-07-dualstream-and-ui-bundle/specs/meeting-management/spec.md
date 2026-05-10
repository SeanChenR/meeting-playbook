## ADDED Requirements

### Requirement: Meeting carries optional scheduled start and end timestamps

The `meeting` table SHALL persist two optional timestamp columns: `scheduled_start_at` and `scheduled_end_at`, both `TIMESTAMP WITH TIME ZONE NULL`. These columns capture when a meeting is planned to occur (distinct from `created_at` which is when the row was created, and distinct from `started_at` / `ended_at` which capture actual session wall-clock times). Existing meeting rows created before this capability SHALL retain `NULL` in both new columns; no backfill SHALL be performed by the migration.

The `POST /api/meetings` endpoint SHALL accept two optional ISO 8601 timestamp fields `scheduled_start_at` and `scheduled_end_at` in its request body. When omitted, both columns SHALL be persisted as `NULL`. When provided, the values SHALL be persisted as parsed timezone-aware timestamps. The `GET /api/meetings` (list) and `GET /api/meetings/{id}` (detail) endpoints SHALL include both fields in their response payloads (as ISO 8601 strings or `null`).

The `MeetingRepository.create()` method signature SHALL accept two new optional keyword arguments `scheduled_start_at: datetime | None = None` and `scheduled_end_at: datetime | None = None`. The repository's read methods (`get_for_user`, `list_for_user`) SHALL include both columns in returned dataclasses.

#### Scenario: Create with both schedule fields persists them

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z", "scheduled_end_at": "2026-06-15T15:00:00Z"}`
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include `scheduled_start_at = "2026-06-15T14:00:00Z"` and `scheduled_end_at = "2026-06-15T15:00:00Z"`, and the database row SHALL store those timezone-aware values

#### Scenario: Create without schedule fields stores NULL

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean"}` (no schedule fields)
- **THEN** the response SHALL be HTTP 201 with `scheduled_start_at = null` and `scheduled_end_at = null` in the response body; the database row SHALL hold `NULL` in both columns

#### Scenario: List endpoint returns schedule fields for every row

- **GIVEN** the authenticated user owns three meetings: one with both schedule fields set, one with only `scheduled_start_at` set, and one with both null
- **WHEN** the user sends `GET /api/meetings`
- **THEN** the response SHALL include all three meetings and each item in the array SHALL contain both `scheduled_start_at` and `scheduled_end_at` keys (with values or `null`)

#### Scenario: Migration adds nullable columns without affecting existing rows

- **GIVEN** the `meeting` table holds existing rows from prior slices
- **WHEN** Alembic migration `0004_add_meeting_scheduled_times` upgrades the schema
- **THEN** both `scheduled_start_at` and `scheduled_end_at` columns SHALL exist with type `TIMESTAMP WITH TIME ZONE`, nullable, and every existing row SHALL contain `NULL` in both columns; the downgrade SHALL drop both columns
