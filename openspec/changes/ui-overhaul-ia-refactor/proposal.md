## Why

The 26-slice build left the navigation surface fragmented in two concrete ways:

1. `/calendar/import` (file: `routes/calendar/upcoming.tsx`, formerly `/calendar/upcoming`) is now a thin wrapper around `CalendarIntegrationPanel` — the **same** panel rendered inside `/settings/integrations`. Two URLs for the same Google Calendar connection surface, plus a "從行事曆匯入" button on `/meetings` that points to the duplicate route.
2. Recordings are scattered: each Recording row lives only inside its source meeting's detail page, so a user inside the 30-day Recording window who wants to "find every recording from last week" has no entry point. The Recording window is a first-class retention concept (per `recording-retention` spec) but the UI does not expose it.

This change is P4 of the 4-phase UI Overhaul roadmap (per `DESIGN.md` §6). It is **pure information-architecture**: routing, navigation links, one new index page, one new backend endpoint pair. P1 tokens / P2 primitives / P3 effect-layer components are out of scope here — this change consumes whatever P1 ships and adds no new visual language.

Per `UI-OVERHAUL-DECISIONS.md`:
- **A1** ✓ — kill the duplicate `/calendar/import` route; calendar integration lives only at `/settings/integrations`. The `/meetings?view=calendar` meeting-calendar view already exists (per `meetings-calendar-view` spec) and is unchanged.
- **A2** — Dashboard stays as-is. Out of scope.
- **A3** — Settings stays flat at 7 items. Out of scope.
- **A4** ✓ — new `/recordings` page indexing the entire Recording window with search + single/batch download.

## What Changes

### A1 — remove duplicate calendar route

- **BREAKING**: remove route `/calendar/import` (the standalone wrapper). The file `packages/web/src/routes/calendar/upcoming.tsx` and its test `upcoming.test.tsx` are deleted. The route entry in `packages/web/src/route-tree.tsx` (`calendarImportRoute`) is removed.
- Update the "從行事曆匯入" / "Import from calendar" button on `packages/web/src/routes/meetings/list.tsx` (currently `to="/calendar/import"`) to navigate to `/settings/integrations` instead.
- The `CalendarIntegrationPanel` component itself is unchanged; only the standalone route is dropped. `/settings/integrations` keeps the panel.
- No changes to `/meetings/calendar` (the calendar **view** of the meeting list, governed by `meetings-calendar-view`).

### A4 — new `/recordings` page

- New route `/recordings` registered in `route-tree.tsx`, rendered inside `ProtectedShell`.
- New page component `packages/web/src/routes/recordings/index.tsx` plus colocated tests.
- New nav link in `protected-shell.tsx` between Meetings and Dashboard, label `recordings` (zh-TW "錄音檔" / en "Recordings").
- Page surfaces every Recording row owned by the authenticated user whose `deleted_at IS NULL` and whose recording is still inside the Recording window (per `recording-retention` rules). Each row shows: capture date (`recording.started_at` or `meeting.scheduled_start` fallback), source meeting title (link to `/meetings/:id`), counterparty label, duration, file size, stream channel (`me` / `counterparty`).
- Filters: free-text search over meeting title (ILIKE), date range (`since` / `until` query params bound to URL state).
- Pagination: cursor or page-based, page size 25.
- Single download: per-row "Download" action hits the existing `GET /api/meetings/{id}/recordings/{recording_id}/audio` endpoint (no new backend path needed for single download).
- Batch download: multi-select checkboxes + bulk action triggers `POST /api/recordings/batch-download` (new endpoint), which streams a zip of selected recordings.
- Stream channel enforcement: rows render only `recording.stream IN ('me', 'counterparty')`. The legacy value `'them'` is **rejected** at API and UI layers (consistent with current domain glossary).

### New backend endpoints

- `GET /api/recordings` — list current-user recordings within the Recording window, accepts `since`, `until`, `search`, `page`, `page_size`. Reuses existing recording authorization (user must own the source meeting).
- `POST /api/recordings/batch-download` — accepts `{ recording_ids: string[] }`, validates ownership + Recording-window membership for each id, streams a zip of WAV files. Hard cap on total selected uncompressed size (see Impact for OOM mitigation).

### Domain + i18n

- All new user-visible strings added to **both** `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json` under a new `recordings` group, plus updates to existing nav strings. Locale-parity test (`locales.test.ts`) gates CI as usual.
- Vocabulary stays inside the project glossary: **Recording window** (not "TTL" / "expiry"), **Counterparty** / **Me**, **Recording** (singular noun for the artifact).

## Capabilities

### New Capabilities

- `recording-index`: User-facing index of every Recording inside the active Recording window. Owns search, date filter, pagination, single-download, batch-download (zip) requirements. Adds `GET /api/recordings` and `POST /api/recordings/batch-download` contract. Stream channel restricted to `me` / `counterparty`.

### Modified Capabilities

- `recording-retention`: Add requirements clarifying that the new `/recordings` index MUST exclude soft-deleted and Recording-window-expired rows, and that batch-download MUST refuse any recording whose retention has expired (HTTP 410 parity with the existing single-recording audio endpoint).
- `meetings-calendar-view`: Add a requirement that the "Import from calendar" affordance on `/meetings` SHALL navigate to `/settings/integrations`, not to a standalone `/calendar/*` route. The reciprocal Kanban / Calendar toggle is unchanged.
- `settings-shell`: Add a requirement that calendar integration SHALL be reachable solely via `/settings/integrations`, removing the duplicate standalone entry point.

## Impact

### Frontend (`packages/web`)

- New: `src/routes/recordings/index.tsx` + `src/routes/recordings/index.test.tsx`.
- New: `src/lib/recordings-api.ts` (query + mutation hooks for `GET /api/recordings` and `POST /api/recordings/batch-download`).
- Deleted: `src/routes/calendar/upcoming.tsx`, `src/routes/calendar/upcoming.test.tsx`.
- Modified: `src/route-tree.tsx` — drop `calendarImportRoute`, register new `recordingsRoute`.
- Modified: `src/routes/meetings/list.tsx` — redirect "Import from calendar" button to `/settings/integrations`.
- Modified: `src/components/protected-shell.tsx` — drop any `/calendar/*` link (if present), add `/recordings` link.
- Modified locales (both files, parity-enforced):
  - `recordings.list.heading`, `recordings.list.empty`, `recordings.list.searchPlaceholder`, `recordings.list.dateRange.since`, `recordings.list.dateRange.until`, `recordings.list.columns.{date,meeting,counterparty,duration,size,stream}`, `recordings.list.action.{download,batchDownload,viewMeeting}`, `recordings.list.streamBadge.{me,counterparty}`, `recordings.list.batch.{selectedCount,confirm,zipReady,oversize}`.
  - `nav.recordings` (sidebar label).
  - `errors.recording.batchOversize`, `errors.recording.retentionExpired`.

### Backend (`packages/backend`)

- New router module exposing `GET /api/recordings` and `POST /api/recordings/batch-download`.
- New service layer reusing existing `RecordingRepository` for authorization + retention checks.
- Batch-download endpoint streams a zip via `zipfile.ZipFile` in `STORED` mode (no in-memory buffering of the full archive), with a hard cap: reject the request with `errors.recording.batchOversize` if the sum of selected recordings' uncompressed bytes exceeds a configurable `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` (default 2 GiB, suitable for 30-day window on a single user). OOM mitigation design lives in `design.md`.
- New configuration: `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` (env var, default 2147483648 = 2 GiB).
- No schema migration. `recording` table already has `stream`, `started_at`, `byte_size`, `duration_ms`, `deleted_at` per `recording-retention` spec.

### Auth gateway (`packages/auth`)

- Proxy `/api/recordings/**` to backend (current gateway already forwards `/api/**` so likely no change; verify in tasks).

### Tests

- Unit + integration tests for the new endpoints (FastAPI test client).
- Frontend route tests for `/recordings` (rendering, search, batch select, download trigger).
- Locale-parity test continues to gate.
- Removal tests: deleting `/calendar/import` route — adjust `routes-i18n.test.tsx` if it references the removed route.

### Out of scope (explicitly)

- No changes to design tokens (P1).
- No changes to Dialog / Popover / Tooltip / Toast / Progress / Theme toggler / Calendar picker primitives (P2).
- No changes to Stars background / Animated list / Bar visualizer / Transcript viewer / Card hover / Button hover / Input style / Success result / Glass dock effect layers (P3).
- No changes to meeting detail page layout (P5).
- No changes to Dashboard (A2 decision).
- No changes to Settings sub-nav structure (A3 decision).
- No new `recording-retention` retention rules — just clarifying that the new index respects them.
- No transcoding, format conversion, or recording editing.
