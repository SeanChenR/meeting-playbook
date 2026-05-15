## MODIFIED Requirements

### Requirement: Meeting carries optional scheduled start and end timestamps

The `meeting` table SHALL persist `scheduled_start_at` as `TIMESTAMP WITH TIME ZONE NOT NULL` and `scheduled_end_at` as `TIMESTAMP WITH TIME ZONE NULL`. The `scheduled_start_at` column captures when a meeting is planned to begin and SHALL always be present (distinct from `created_at` which is when the row was created, and distinct from `started_at` / `ended_at` which capture actual session wall-clock times). The `scheduled_end_at` column remains optional and represents when the meeting is planned to finish.

The `POST /api/meetings` endpoint SHALL require a `scheduled_start_at` field as an ISO 8601 timestamp in its request body and SHALL reject any request that omits it or supplies `null` with HTTP 422 and `error_code = "meeting.scheduled_start_at.required"`. The endpoint SHALL accept `scheduled_end_at` as an optional ISO 8601 timestamp; when omitted, the column SHALL be persisted as `NULL`. When both fields are provided in the same request, the backend SHALL reject the request with HTTP 422 and `error_code = "meeting.invalid_time_range"` if `scheduled_end_at < scheduled_start_at`. The `GET /api/meetings` (list) and `GET /api/meetings/{id}` (detail) endpoints SHALL include both fields in their response payloads; `scheduled_start_at` SHALL always be a non-null ISO 8601 string, while `scheduled_end_at` SHALL be a string or `null`.

The `MeetingRepository.create()` method signature SHALL accept `scheduled_start_at: datetime` as a required keyword argument and `scheduled_end_at: datetime | None = None` as optional. The repository's read methods (`get_for_user`, `list_for_user`) SHALL include both columns in returned dataclasses.

Pre-existing meeting rows that contained `NULL` in `scheduled_start_at` before this requirement landed SHALL be backfilled to the row's `created_at` value by the migration that establishes the NOT NULL constraint. Once backfilled, the original NULL state SHALL NOT be recoverable; downgrading the column to nullable SHALL NOT restore NULLs in previously-backfilled rows.

#### Scenario: Create with both schedule fields persists them

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z", "scheduled_end_at": "2026-06-15T15:00:00Z"}`
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include `scheduled_start_at = "2026-06-15T14:00:00Z"` and `scheduled_end_at = "2026-06-15T15:00:00Z"`, and the database row SHALL store those timezone-aware values

#### Scenario: Create without scheduled_start_at is rejected

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean"}` (no `scheduled_start_at`)
- **THEN** the response status SHALL be HTTP 422 and the response body SHALL contain `error_code = "meeting.scheduled_start_at.required"` and no row SHALL be inserted

#### Scenario: Create with end-before-start is rejected

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T15:00:00Z", "scheduled_end_at": "2026-06-15T14:00:00Z"}`
- **THEN** the response status SHALL be HTTP 422 and the response body SHALL contain `error_code = "meeting.invalid_time_range"` and no row SHALL be inserted

#### Scenario: Create without scheduled_end_at stores NULL only for end

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z"}` (no `scheduled_end_at`)
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include the supplied `scheduled_start_at` and `scheduled_end_at = null`; the database row SHALL hold the timezone-aware start value and `NULL` in `scheduled_end_at`

#### Scenario: List endpoint returns schedule fields for every row

- **GIVEN** the authenticated user owns three meetings whose `scheduled_start_at` values are all non-null, one with `scheduled_end_at` set and two with `scheduled_end_at = NULL`
- **WHEN** the user sends `GET /api/meetings`
- **THEN** the response SHALL include all three meetings and each item SHALL contain a non-null `scheduled_start_at` ISO 8601 string and a `scheduled_end_at` that is either an ISO 8601 string or `null`

#### Scenario: Migration backfills pre-existing NULL rows and enforces NOT NULL

- **GIVEN** the `meeting` table holds rows from prior slices, including some with `scheduled_start_at IS NULL`
- **WHEN** Alembic migration `0012_meeting_start_not_null` upgrades the schema in a single transaction
- **THEN** every previously-NULL `scheduled_start_at` SHALL be set to that row's `created_at` value, the column SHALL afterwards have `NOT NULL` enforced at the database level, and a subsequent `SELECT COUNT(*) FROM meeting WHERE scheduled_start_at IS NULL` SHALL return `0`; the downgrade SHALL drop the NOT NULL constraint but SHALL NOT revert backfilled values to NULL

### Requirement: /meetings SHALL render meetings as a 3-column date-bucketed Kanban

The `/meetings` route SHALL render meetings as a 3-column Kanban board grouped by **lifecycle state**, not by time window.

The three columns SHALL be, in left-to-right visual order:

- **待補錄** (`needs_recording`) — meetings whose `status` is `"scheduled"` AND whose `scheduled_start_at` is strictly less than `now`. Semantic: the scheduled time has already passed but no recording session has begun, so the meeting either needs a follow-up recording (offline ingest or manual entry) or needs to be removed. Column accent: primary.
- **未來** (`upcoming`) — meetings whose `status` is `"scheduled"` AND whose `scheduled_start_at` is greater than or equal to `now`. Semantic: all future commitments that have not yet started. Column accent: muted-foreground.
- **已結束** (`completed`) — meetings whose `status` is one of `"in_progress"` or `"completed"`. Semantic: any meeting whose recording session has been started (regardless of whether it has been finalized) is treated as "actually happened" and SHALL be classified here, independent of `scheduled_start_at`. Column accent: secondary.

Bucket assignment SHALL be implemented by a pure helper function `getMeetingDateBucket(meeting, now)` exported from `packages/web/src/lib/meetings-bucket.ts`. The helper SHALL be called from the Kanban component during render with `now = new Date()`. The helper SHALL return one of the three literal strings `"needs_recording"`, `"upcoming"`, `"completed"` and SHALL NOT return any other value.

The Kanban component SHALL display column headers using the i18n keys `meetings.kanban.bucketNeedsRecording`, `meetings.kanban.bucketUpcoming`, `meetings.kanban.bucketCompleted` (in that left-to-right order). The legacy keys `meetings.kanban.bucketUpcoming`, `meetings.kanban.bucketFuture`, `meetings.kanban.bucketPast` SHALL be removed from both `zh-TW.json` and `en.json` to prevent the analyzer from missing dead translations. The 7-day window constant `SEVEN_DAYS_MS` SHALL be removed from `meetings-bucket.ts`.

The "已結束" column SHALL sort its meetings by `scheduled_start_at` in descending order (most recent first), reusing the existing `_sortPastDesc` helper renamed to `_sortCompletedDesc`. The other two columns SHALL render in the order returned by the backend list endpoint.

Each column SHALL render a header with the bucket label, a count badge, a vertically scrollable card list, and an empty-state hint. The Kanban container SHALL use `grid-template-columns: repeat(3, minmax(280px, 1fr))`. Drag-and-drop reordering SHALL NOT be supported in this iteration.

#### Scenario: Three-bucket distribution under new rules

- **GIVEN** `now = 2026-05-12T10:00:00 local` and the backend returns five meetings:

  | id | status        | scheduled_start_at        |
  |----|---------------|---------------------------|
  | a  | in_progress   | 2026-04-01T09:00:00       |
  | b  | scheduled     | 2026-05-13T15:00:00       |
  | c  | scheduled     | 2026-05-25T15:00:00       |
  | d  | scheduled     | 2026-05-01T15:00:00       |
  | e  | completed     | 2026-04-15T10:00:00       |

- **WHEN** the /meetings Kanban renders
- **THEN** column 待補錄 SHALL contain meeting `d` (scheduled but `scheduled_start_at < now`)
- **AND** column 未來 SHALL contain meetings `b` and `c` (scheduled with `scheduled_start_at >= now`)
- **AND** column 已結束 SHALL contain meetings `a` (in_progress) and `e` (completed)

#### Scenario: in_progress meeting with past scheduled_start_at falls into 已結束

- **GIVEN** a meeting with `status === "in_progress"` and `scheduled_start_at = "2026-04-01T09:00:00"` and `now = "2026-05-12T10:00:00"`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"completed"` (because `status === "in_progress"` short-circuits before the time comparison)

#### Scenario: Overdue scheduled meeting falls into 待補錄

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at = "2026-05-01T15:00:00"` and `now = "2026-05-12T10:00:00"`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"needs_recording"` (not `"completed"`, because the meeting was never started)

#### Scenario: Scheduled meeting at exactly now falls into 未來

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at` equal to `now` (boundary case)
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"upcoming"` (the comparison is `scheduled_start_at >= now`, half-open in the future direction)

#### Scenario: Invalid scheduled_start_at string falls into 待補錄 as safe default

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at = "not-a-date"` so `Date.parse` returns `NaN`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"needs_recording"` as a safe default (instead of the previous `"past"` default, since malformed time is treated as "we have no idea when this is meant to happen → needs human attention")
- **AND** SHALL emit a `console.warn` in dev (when `import.meta.env.DEV`)

## ADDED Requirements

### Requirement: PATCH /api/meetings/{id} accepts partial updates to title, scheduled times, display names, and asr_provider

The backend SHALL expose `PATCH /api/meetings/{id}` accepting a JSON body with up to six optional fields: `title`, `scheduled_start_at`, `scheduled_end_at`, `counterparty_display_name`, `me_display_name`, `asr_provider`. Any subset of these fields (zero or more) SHALL be accepted; fields that are absent from the request body SHALL leave the corresponding column unchanged. A request with an empty body (no fields supplied) SHALL be treated as a no-op and SHALL return HTTP 200 with the current persisted meeting. Each string field, when present, SHALL be stripped of surrounding whitespace and SHALL NOT be empty after stripping; otherwise the endpoint SHALL respond with HTTP 422 and `error_code = "meeting.invalid_field"`. The endpoint SHALL validate that, after merging the request body with the current row, `scheduled_end_at` (if non-null) is greater than or equal to `scheduled_start_at`; otherwise the endpoint SHALL respond with HTTP 422 and `error_code = "meeting.invalid_time_range"`. The endpoint SHALL return HTTP 404 with `error_code = "meeting.not_found"` when the meeting does not exist OR is owned by a different user, and MUST NOT distinguish between those two cases. A successful update SHALL return HTTP 200 with the `MeetingDetailRead` response shape (the same shape returned by `GET /api/meetings/{id}`), reflecting the merged state of the row.

#### Scenario: PATCH with title only updates only title

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `title = "Old"`, `counterparty_display_name = "林"`, `me_display_name = "Sean"`, `scheduled_start_at = "2026-06-15T14:00:00Z"`, `asr_provider = "qwen3"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "New"}`
- **THEN** the response status SHALL be HTTP 200, the response body SHALL show `title = "New"` and all other fields unchanged, and the database row SHALL persist `title = "New"` while every other column SHALL be byte-identical to its prior value

#### Scenario: PATCH with multiple fields updates them atomically

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "Updated", "scheduled_start_at": "2026-07-01T09:00:00Z", "scheduled_end_at": "2026-07-01T10:00:00Z", "me_display_name": "S. Chen"}`
- **THEN** the response status SHALL be HTTP 200 and all four supplied fields SHALL be reflected in the response body and in a single subsequent SELECT against the row

#### Scenario: PATCH with empty body returns current row

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{}`
- **THEN** the response status SHALL be HTTP 200 and the response body SHALL be byte-identical to the body returned by `GET /api/meetings/m_x` immediately prior

#### Scenario: PATCH with empty title is rejected

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "   "}`
- **THEN** the response status SHALL be HTTP 422, the response body SHALL contain `error_code = "meeting.invalid_field"`, and the meeting row SHALL be unchanged

#### Scenario: PATCH with end-before-start is rejected even when only end is supplied

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `scheduled_start_at = "2026-06-15T15:00:00Z"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"scheduled_end_at": "2026-06-15T14:00:00Z"}`
- **THEN** the response status SHALL be HTTP 422, the response body SHALL contain `error_code = "meeting.invalid_time_range"`, and `scheduled_end_at` SHALL remain at its prior value

#### Scenario: PATCH on a meeting owned by another user returns 404

- **GIVEN** meeting `m_y` is owned by user `u_b`
- **WHEN** user `u_a` sends `PATCH /api/meetings/m_y` with body `{"title": "Hijack"}`
- **THEN** the response status SHALL be HTTP 404, the response body SHALL contain `error_code = "meeting.not_found"`, and the row owned by `u_b` SHALL be unchanged

#### Scenario: PATCH with asr_provider only retains slice-11 behavior

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `asr_provider = "qwen3"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"asr_provider": "whisper"}`
- **THEN** the response status SHALL be HTTP 200, the response body SHALL show `asr_provider = "whisper"`, and the database row SHALL persist `asr_provider = "whisper"`

### Requirement: MeetingRepository.update_for_user writes any subset of mutable meeting fields in a single UPDATE

The backend SHALL provide `async MeetingRepository.update_for_user(*, user_id: str, meeting_id: str, fields: dict[str, Any]) -> Meeting | None` at `packages/backend/meeting_playbook/meetings/repository.py`. The method SHALL accept a dictionary whose keys are a subset of `{"title", "scheduled_start_at", "scheduled_end_at", "counterparty_display_name", "me_display_name", "asr_provider"}` and SHALL emit a single SQL `UPDATE` statement scoped to `(id = meeting_id AND user_id = user_id)`. When `fields` is empty, the method SHALL skip the UPDATE and SHALL return the result of `get_for_user(user_id=user_id, meeting_id=meeting_id)`. When `fields` is non-empty and the meeting does not exist OR is owned by another user, the method SHALL return `None`. When the update succeeds, the method SHALL return the refreshed `Meeting` row reflecting all committed columns. The existing `update_asr_provider_for_user` method SHALL be retained as a thin wrapper that delegates to `update_for_user(fields={"asr_provider": <value>})` so slice-11 callers and tests remain functional.

#### Scenario: update_for_user with empty fields returns the row unchanged

- **GIVEN** a meeting `m_x` owned by `u_a` with `title = "Original"`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_x", fields={})` runs
- **THEN** the call SHALL emit zero UPDATE statements (verified by SQLAlchemy event listener), the returned `Meeting` SHALL have `title = "Original"`, and no other row SHALL be modified

#### Scenario: update_for_user with multiple fields emits one UPDATE

- **GIVEN** a meeting `m_x` owned by `u_a`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_x", fields={"title": "T2", "me_display_name": "S2"})` runs
- **THEN** the call SHALL emit exactly one UPDATE statement (verified by SQLAlchemy event listener), the returned `Meeting` SHALL have `title = "T2"` and `me_display_name = "S2"`, and a subsequent SELECT SHALL confirm both columns

#### Scenario: update_for_user across owners returns None

- **GIVEN** a meeting `m_y` owned by `u_b`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_y", fields={"title": "Hijack"})` runs
- **THEN** the call SHALL return `None` and the row owned by `u_b` SHALL be unchanged

#### Scenario: update_asr_provider_for_user still works after refactor

- **GIVEN** a meeting `m_x` owned by `u_a` with `asr_provider = "qwen3"`
- **WHEN** `repo.update_asr_provider_for_user(user_id="u_a", meeting_id="m_x", asr_provider="whisper")` runs
- **THEN** the returned `Meeting` SHALL have `asr_provider = "whisper"` and the database row SHALL persist the new value

### Requirement: Meeting list, kanban, and calendar views render scheduled_start_at without created_at fallback

The web client SHALL render scheduled-time displays for a meeting solely from `meeting.scheduled_start_at` and SHALL NOT fall back to `meeting.created_at` for any view, sort key, or date bucket. The `MeetingCard` component SHALL format the scheduled start time using `meeting.scheduled_start_at` only. The Kanban view (`MeetingsKanban`) SHALL sort and bucket meetings by `meeting.scheduled_start_at` only. The Calendar view (`meetings-calendar-utils.toCalendarEvent`) SHALL build calendar events from `meeting.scheduled_start_at` only and SHALL treat the value as guaranteed non-null after slice-15 lands. The TypeScript type for `Meeting.scheduled_start_at` SHALL be narrowed from `string | null` to `string`.

#### Scenario: MeetingCard renders the scheduled start, not created_at

- **GIVEN** a meeting with `scheduled_start_at = "2026-06-15T14:00:00Z"` and `created_at = "2026-05-01T00:00:00Z"`
- **WHEN** `<MeetingCard meeting={meeting} />` renders
- **THEN** the rendered time text SHALL be derived from `2026-06-15T14:00:00Z` and SHALL NOT mention `2026-05-01T00:00:00Z`

#### Scenario: Kanban sorts by scheduled_start_at and never by created_at

- **GIVEN** two meetings `A` and `B`, where `A.scheduled_start_at = "2026-07-01T00:00:00Z"` and `A.created_at = "2026-01-01T00:00:00Z"`, while `B.scheduled_start_at = "2026-06-01T00:00:00Z"` and `B.created_at = "2026-08-01T00:00:00Z"`
- **WHEN** `MeetingsKanban` renders both meetings in the same column
- **THEN** the visual order SHALL place `A` after `B` (because `A.scheduled_start_at > B.scheduled_start_at`), confirming that `created_at` is not consulted

#### Scenario: Calendar event helper returns an event for every row after slice-15

- **GIVEN** a meeting row whose `scheduled_start_at` is a valid ISO 8601 string (guaranteed by NOT NULL constraint)
- **WHEN** `toCalendarEvent(meeting)` runs
- **THEN** the call SHALL return a non-null calendar event object whose `start` field equals `meeting.scheduled_start_at`

### Requirement: meeting detail page lets the user inline-edit title, scheduled times, and display names

The web client SHALL provide an inline edit form on the meeting detail route (`/meetings/$meetingId`) that lets the authenticated user change `title`, `scheduled_start_at`, `scheduled_end_at`, `counterparty_display_name`, and `me_display_name` for the meeting they own. The form SHALL be implemented as a React component at `packages/web/src/components/meeting-edit-form.tsx`, accept the current `Meeting` as a prop, validate inputs with a zod schema that mirrors the backend rules (non-empty trimmed strings; `scheduled_end_at >= scheduled_start_at` when both present), and submit to `PATCH /api/meetings/{id}` only the fields that the user changed. On a successful response the component SHALL invalidate the React Query caches keyed `["meetings"]` and `["meeting", meetingId]` so all three list views (List / Kanban / Calendar) and the detail page reflect the change without a full page reload. On a non-200 response the component SHALL surface the localized error message via `localizedErrorMessage(error_code, t)` and SHALL leave the form open with the user's draft intact. All user-visible strings introduced by this form SHALL exist in both `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` under the `meetings.edit.*` namespace.

#### Scenario: Edit form saves a changed title and updates the cache

- **GIVEN** the authenticated user is viewing `/meetings/m_x` for a meeting whose `title = "Old"` and clicks the Edit toggle
- **WHEN** the user changes `title` to `"New"` and clicks Save
- **THEN** the component SHALL send `PATCH /api/meetings/m_x` with body `{"title": "New"}`, SHALL render a localized "Saved" confirmation on HTTP 200, and SHALL invalidate the React Query caches `["meetings"]` and `["meeting", "m_x"]` such that returning to the list view shows the new title

#### Scenario: Edit form rejects end-before-start client-side before sending

- **GIVEN** the authenticated user is editing meeting `m_x` with `scheduled_start_at = "2026-06-15T15:00:00Z"`
- **WHEN** the user sets `scheduled_end_at` to `"2026-06-15T14:00:00Z"` and clicks Save
- **THEN** the component SHALL block the request, render the localized `errors.meeting.invalidTimeRange` message next to the `scheduled_end_at` field, and SHALL NOT call `PATCH /api/meetings/m_x`

#### Scenario: Edit form surfaces a server-side 422 in the localized error message

- **GIVEN** the authenticated user submits an edit for meeting `m_x`
- **WHEN** the server responds with HTTP 422 and body `{"error_code": "meeting.invalid_field", "message": "..."}`
- **THEN** the form SHALL remain open with the user's input intact, render the localized message for `meeting.invalid_field`, and re-enable the Save button so the user can correct and retry

### Requirement: meeting detail edit form opens as a centered modal dialog

The `<MeetingEditForm>` component, when triggered from the meeting detail route's Edit toolbar button, SHALL render inside a shadcn `<Dialog>` modal that is centered on the viewport. The dialog SHALL include a `<DialogTitle>` displaying the localized string `meetings.edit.dialogTitle` and a `<DialogDescription>` displaying `meetings.edit.dialogDescription`. The dialog SHALL be dismissible by pressing the Escape key, clicking the backdrop, clicking the Cancel button, or successfully saving (a 200 response from `PATCH /api/meetings/{id}`). The dialog SHALL NOT push the underlying page layout. While the dialog is open, the rest of the detail page SHALL be visible but covered by a semi-transparent backdrop. The dialog SHALL be a sibling of the detail page content (not nested inside a transformed parent) so the centering math is unaffected by scroll position.

#### Scenario: Clicking Edit opens the dialog and rendering the form

- **GIVEN** the authenticated user is viewing `/meetings/m_x` with the edit toggle visible
- **WHEN** the user clicks the toolbar Edit button
- **THEN** a shadcn `<Dialog>` SHALL open centered on the viewport, the dialog title SHALL read the localized string for `meetings.edit.dialogTitle`, the form's five fields SHALL be pre-filled with the meeting's current values, and the page below SHALL be covered by a semi-transparent backdrop

#### Scenario: Pressing Escape closes the dialog

- **GIVEN** the edit dialog is open with a draft change to the title
- **WHEN** the user presses the Escape key
- **THEN** the dialog SHALL close, the draft SHALL be discarded, and no `PATCH /api/meetings/m_x` request SHALL be sent

### Requirement: meeting detail actions bar always renders an upload-audio button

The meeting detail route SHALL render a persistent "Upload audio" button inside the `<MetadataCard>` actions row for every meeting, regardless of the meeting's `status` value. The detail page SHALL pass a `<Button>` element into the `<MetadataCard>` component's new `uploadSlot` prop; the button SHALL have `data-testid="metadata-upload-audio"` and SHALL render the localized label `meetings.session.uploadAudio`. Clicking the button SHALL open the existing `<UploadDialog>` by setting the detail page's `offlineIngestOpen` state to `true`.

The button's visual treatment SHALL adapt to `meeting.status`:

- `status === "scheduled"` → variant `"outline"`, `disabled = false`
- `status === "in_progress"` → variant `"outline"`, `disabled = true` (offline ingest is not allowed while live capture is running; double-writing the `recording` child table would create ambiguous source rows)
- `status === "completed"` → variant `"secondary"`, `disabled = false` (re-ingest is allowed for re-running ASR on completed meetings)

The legacy `<UploadBanner>` component and its `shouldShowOfflineIngestBanner(meeting, now)` predicate SHALL be removed from the codebase along with their tests. The locale keys `offline_ingest.banner.heading`, `offline_ingest.banner.subhead`, `offline_ingest.banner.cta` SHALL be removed from both `zh-TW.json` and `en.json`.

#### Scenario: Upload button is outline-enabled for scheduled meetings

- **GIVEN** a meeting `m_x` with `status = "scheduled"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** a button with `data-testid="metadata-upload-audio"` SHALL be present, SHALL carry the `outline` variant class, SHALL NOT be disabled, and SHALL display the localized text for `meetings.session.uploadAudio`

#### Scenario: Upload button is disabled while in_progress

- **GIVEN** a meeting `m_x` with `status = "in_progress"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** the upload button SHALL be present but `disabled = true`, and clicking SHALL NOT open the upload dialog

#### Scenario: Upload button is secondary-enabled for completed meetings

- **GIVEN** a meeting `m_x` with `status = "completed"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** the upload button SHALL be present, SHALL carry the `secondary` variant class, SHALL NOT be disabled, and clicking SHALL open the upload dialog (used for re-running ASR)

### Requirement: needs_recording kanban cards offer a hover-only upload shortcut and a custom empty CTA

`<MeetingCard>` SHALL accept a `showUploadShortcut?: boolean` prop. When `showUploadShortcut === true`, the card SHALL render a small button with `data-testid="meeting-card-upload-shortcut"` displaying the localized label `meetings.kanban.uploadShortcut`. The button SHALL be visually hidden by default (`opacity-0`) and SHALL fade in only when the card root is hovered (`group-hover:opacity-100 transition-opacity`). Clicking the button SHALL navigate to `/meetings/$id` with `search = { action: "upload" }` for the card's meeting id; clicking SHALL NOT propagate to the card's primary link. When `showUploadShortcut !== true` (default), the card SHALL NOT render the shortcut button at all (DOM-absent, not just hidden).

`<MeetingsKanban>` SHALL pass `showUploadShortcut={true}` to every `<MeetingCard>` rendered inside the `needs_recording` column and `showUploadShortcut={false}` (or omit the prop) for `upcoming` and `completed` columns.

The meeting detail route SHALL read `useSearch().action`; when `action === "upload"`, the route SHALL set `offlineIngestOpen` to `true` on mount AND SHALL clear the `action` query param via `navigate({ search: { action: undefined }, replace: true })` so that page reloads do not re-trigger the dialog.

When the `needs_recording` column has zero meetings, `<MeetingsKanban>` SHALL render the localized string `meetings.kanban.bucketNeedsRecordingEmpty` (zh-TW: "目前沒有待補錄的會議"; en: "No meetings to follow up on") instead of the shared `meetings.kanban.bucketEmpty` hint. The `upcoming` and `completed` columns SHALL continue to use `meetings.kanban.bucketEmpty` when empty.

#### Scenario: needs_recording card mounts the hover shortcut

- **GIVEN** a meeting `m_x` with `status = "scheduled"` and `scheduled_start_at < now` so it lands in the needs_recording bucket
- **WHEN** the Kanban renders `<MeetingCard meeting={m_x} showUploadShortcut={true} />`
- **THEN** a button with `data-testid="meeting-card-upload-shortcut"` SHALL exist in the DOM with class `opacity-0` AND class `group-hover:opacity-100`

#### Scenario: Clicking the shortcut navigates with action=upload

- **GIVEN** a needs_recording card is rendered with the hover shortcut
- **WHEN** the user clicks `data-testid="meeting-card-upload-shortcut"`
- **THEN** the router SHALL navigate to `/meetings/m_x` with `search = { action: "upload" }`, and the click handler SHALL call `event.stopPropagation()` so the card's primary link does NOT also fire

#### Scenario: Detail page reads action=upload and auto-opens the dialog

- **GIVEN** the detail route mounts with `useSearch().action === "upload"`
- **WHEN** the route's mount effect runs
- **THEN** `offlineIngestOpen` SHALL be set to `true`, the upload dialog SHALL open, AND the route SHALL call `navigate({ search: { action: undefined }, replace: true })` to scrub the query so subsequent reloads do not re-fire

#### Scenario: needs_recording empty column shows the custom CTA

- **GIVEN** no meeting in the user's data set falls into the needs_recording bucket
- **WHEN** the Kanban renders the empty needs_recording column
- **THEN** the column body SHALL contain `data-testid="kanban-empty-needs_recording"` AND its text SHALL be the localized string for `meetings.kanban.bucketNeedsRecordingEmpty` (NOT `meetings.kanban.bucketEmpty`)
