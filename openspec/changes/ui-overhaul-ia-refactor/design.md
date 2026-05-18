## Context

Meeting Playbook's UI was assembled across 26 vertical slices plus 4 follow-up refactors. The result works, but the navigation surface carries vestigial seams from the build order:

- The Google Calendar connection flow was originally a standalone page at `/calendar/upcoming` (slice-7). It later moved under `/calendar/import` and was decomposed into a reusable `CalendarIntegrationPanel`. That panel is now rendered in **both** `/calendar/import` and `/settings/integrations`. The standalone route survives only because nothing has removed it; the meeting list's "從行事曆匯入" button still points there.
- The Recording window is governed by `recording-retention` (30-day retention, soft-delete via `deleted_at`, retention job, 410 Gone on the audio endpoint when expired). The retention rule is a first-class product concept ("錄音檔保留 30 天"), but the UI exposes recordings only as nested rows inside each meeting's detail page. A user inside the Recording window has no way to answer "what recordings do I still have, across all meetings?" — the conceptual entity exists in the spec, but not in the navigation.

This is P4 of the 4-phase UI Overhaul (per `DESIGN.md` §6). P1 (tokens), P2 (primitives), and P3 (effect layers) own the visual language; P4 owns only routes, links, and one new index page.

The user's `UI-OVERHAUL-DECISIONS.md` worksheet locks in: A1 = kill duplicate, A4 = add `/recordings`, A2 = dashboard untouched, A3 = settings flat.

### Existing capabilities cross-referenced

- `recording-retention/spec.md` — 30-day window, `deleted_at`, retention job, 410 Gone, frontend disabled play affordance, export bundle exclusion rule.
- `meetings-calendar-view/spec.md` — `/meetings/calendar` view + Kanban/Calendar toggle.
- `settings-shell/spec.md` — flat 7-item settings sub-nav (`profile`, `security`, `preferences`, `data`, `integrations`, `voice`, `tags`).
- `calendar-integration/spec.md` — `GET /api/calendar/upcoming` data contract and `CalendarIntegrationPanel`.

## Goals / Non-Goals

**Goals:**

- Single canonical entry point for Google Calendar connection: `/settings/integrations`.
- Single canonical entry point for "see every Recording in my Recording window": `/recordings`.
- Zero changes to design tokens or component primitives — this change consumes whatever P1/P2/P3 ship.
- Strict adherence to existing domain glossary: **Recording window**, **Counterparty**, **Me**, **Playbook**.
- i18n parity: every new user-visible string ships in `zh-TW.json` AND `en.json` simultaneously.
- Database stream values restricted to `me` / `counterparty`; the legacy `them` value is rejected at API boundary.
- Bounded memory for batch download (no OOM on a power user's 30-day window).

**Non-Goals:**

- Visual / token / primitive changes (P1 / P2 / P3 own these).
- Meeting detail page layout (P5).
- Dashboard restructure (A2 = no-op).
- Settings sub-nav restructure (A3 = no-op).
- Recording editing, format conversion, transcoding, waveform UI.
- Cross-user recording sharing (out of product scope entirely).
- Restoring the old `/calendar/upcoming` URL via redirect (the URL was internal; no external integrations depend on it — confirmed by repo search).
- Bulk-delete of recordings (retention-only deletion is intentional per `recording-retention`).

## Decisions

### Decision: New capability `recording-index` rather than extending `recording-retention`

`recording-retention` owns the **lifecycle** policy (when a recording becomes inaccessible). The new `/recordings` page is a **read surface** that respects that policy but adds independent requirements (search, batch download, navigation). Conflating them would make `recording-retention` carry UI requirements, which fights the boundary that retention is a backend invariant.

Alternative considered: stuff the new requirements into `recording-retention`. Rejected — pollutes the retention capability with presentation concerns. We do still **modify** `recording-retention` with one tightening clause (batch-download MUST reject expired rows the same way the per-recording audio endpoint does), because that clause is genuinely a retention invariant.

### Decision: Hard remove `/calendar/import`, no redirect

The route is internal; no documented external link, no embed, no email template references it (verified via repo grep). Adding a redirect would create a long-lived backwards-compat surface for a route that has been duplicate-rendered for the entire slice-19 era. We delete the route and update the only outgoing link (`meetings/list.tsx`).

Alternative considered: 301 redirect `/calendar/import` → `/settings/integrations`. Rejected as overengineering — TanStack Router would need a route just to redirect; cheaper to delete and accept that any stale bookmark 404s.

### Decision: Single-recording download reuses existing endpoint

`GET /api/meetings/{id}/recordings/{recording_id}/audio` already exists with full authorization + 410-Gone-on-expired handling (per `recording-retention`). The `/recordings` page builds its per-row download URL using each row's `meeting_id` + `recording_id`. No new single-download endpoint.

Alternative considered: introduce `GET /api/recordings/{recording_id}/audio` (flat). Rejected — would require duplicate authorization logic; the existing nested endpoint is the spec'd path and is already i18n'd via `errors.recording.retentionExpired`.

### Decision: Batch download is a new POST endpoint, not GET, with size cap and streaming zip

- **POST not GET**: the request body carries `recording_ids: string[]` which can exceed practical URL length once a user selects 30+ rows. POST also makes the operation non-idempotent on the server side (creates a transient zip stream) without violating REST expectations.
- **Streaming zip via `zipfile.ZipFile` in `STORED` mode**: WAVs are already large + uncompressible; `STORED` skips deflate to avoid CPU pressure. The zip is written directly to the FastAPI `StreamingResponse` body, so the server's peak memory stays at ~1 WAV file's worth (one read buffer) regardless of total zip size.
- **Hard size cap (`RECORDING_BATCH_DOWNLOAD_MAX_BYTES`, default 2 GiB)**: pre-flight sum of selected `byte_size` values; if it exceeds the cap, return 413 Payload Too Large with error code `errors.recording.batchOversize`. 2 GiB covers a typical 30-day window (e.g., 30 × 1-hour meetings @ ~60 MB WAV ≈ 1.8 GiB) while bounding worst-case server load. Configurable via env so we can tune after observation.

Alternative considered: queued background job that emails a presigned URL when ready. Rejected for now — adds infra (job queue, blob storage, mail) for a user base where 2 GiB ad-hoc downloads are tractable. Revisit if user count grows or recording duration grows.

Alternative considered: server-side merge into a single WAV. Rejected — destroys per-recording metadata (counterparty, started_at) and conflates streams.

### Decision: Stream channel validation at API boundary rejects `'them'`

`recording.stream` is database-level `CHECK (stream IN ('me', 'counterparty'))` per current schema. The new `GET /api/recordings` response and the new `POST /api/recordings/batch-download` both validate that every returned / requested row has `stream IN ('me', 'counterparty')`. Any row with the legacy `'them'` value (should not exist, but defense-in-depth) is filtered out of the list response and triggers a 422 Unprocessable Entity on batch-download. Frontend rendering also asserts on the union type.

This is **not** a retroactive migration — it's a hardening of the read path. A separate change can audit the database if any `them` rows are found in the wild.

### Decision: Recording-window membership computed at query time, not stored

`recording-retention` computes the window by `recording.captured_at >= NOW() - INTERVAL '{RECORDING_RETENTION_DAYS} days' AND deleted_at IS NULL`. The new `GET /api/recordings` reuses the same predicate via the existing `RecordingRepository` (single source of truth). No new column, no denormalization.

### Decision: Free-text search uses ILIKE on `meeting.title`, not full-text

Per the user's directive ("不需要 full text search index"). The query joins `recording → meeting` and applies `meeting.title ILIKE '%' || :q || '%'`. Cost is acceptable because the candidate set is already constrained to one user's last 30 days of recordings — practically O(tens to low hundreds of rows).

If search performance regresses (e.g., per-user recording count grows past ~10k inside the window), revisit with a trigram index. Not blocking.

### Decision: New nav entry placement in `protected-shell.tsx`

Between Meetings and Dashboard, in this order: **Meetings → Recordings → Dashboard → (user menu)**. Rationale: Recordings semantically lives downstream of Meetings (a Meeting produces Recordings); Dashboard is a synthetic aggregate that should sit after the primary entities. The user did not specify ordering in the worksheet, flagging as confirmable.

### Decision: Pagination is page-based, page size 25

Page-based (not cursor) because the result set is small (one user × 30 days), the page is filter-driven (search + date range can mutate stable cursors anyway), and TanStack Router's URL state for `?page=N` is trivial. Page size 25 mirrors `meetings/list.tsx`.

### Decision: URL query state is the source of truth for filters

`?since=YYYY-MM-DD&until=YYYY-MM-DD&search=...&page=N`. Bookmarkable, shareable, back-button friendly. TanStack Router's `validateSearch` parses + types the params.

## Implementation Contract

### Behavior — frontend

- Navigating to `/calendar/import` returns 404 (route no longer registered). No redirect.
- The "從行事曆匯入 / Import from calendar" button on `/meetings` (kanban / calendar / list views) navigates to `/settings/integrations`.
- Navigating to `/recordings` while authenticated renders a list of the current user's recordings inside the Recording window, ordered by `captured_at DESC`, paginated 25 per page. While unauthenticated: redirected through the existing `ProtectedShell` auth flow.
- The page header shows total count + Recording-window summary ("Showing X recordings from the last 30 days").
- Search input (debounced 300ms) filters by meeting title (ILIKE).
- Date range pickers bound to URL `since` / `until`. Empty = open-ended within the Recording window.
- Per-row "Download" action triggers a browser download via the existing `GET /api/meetings/:id/recordings/:rid/audio` endpoint.
- Multi-select checkboxes + "Batch download" action call `POST /api/recordings/batch-download` with selected ids. The response is a `application/zip` stream the browser saves as `recordings-YYYYMMDD-HHmm.zip`.
- If the total selected size exceeds the cap, the backend responds 413 with `error_code: "recording.batch_oversize"` and the frontend shows a toast (using the i18n key `errors.recording.batchOversize`) listing the cap value.
- If any selected recording is retention-expired, backend responds 410 with `error_code: "recording.retention_expired"` and the frontend shows a toast naming the offending count.
- Sidebar nav shows a new entry between Meetings and Dashboard labeled per `nav.recordings` locale key.

### Behavior — backend

**`GET /api/recordings`**
- Auth: existing session middleware; user inferred from session.
- Query params:
  - `since`: ISO date, optional. Defaults to `NOW() - RECORDING_RETENTION_DAYS`.
  - `until`: ISO date, optional. Defaults to `NOW()`.
  - `search`: string, optional. ILIKE on `meeting.title`.
  - `page`: int, default 1.
  - `page_size`: int, default 25, max 100.
- Returns: `{ recordings: RecordingSummary[], total: int, page: int, page_size: int }`.
- `RecordingSummary`: `{ id, meeting_id, meeting_title, counterparty_label, captured_at, duration_ms, byte_size, stream }`.
- Filters: `recording.deleted_at IS NULL AND captured_at >= (NOW() - retention_days) AND stream IN ('me', 'counterparty')`.
- Authorization: `recording → meeting.owner_id = current_user.id`.

**`POST /api/recordings/batch-download`**
- Auth: same.
- Body: `{ recording_ids: string[] }`. Validation: 1 ≤ len(recording_ids) ≤ 200.
- Pre-flight checks (all 4xx if any fail):
  - All ids belong to current user → 403 if any foreign id.
  - All rows still inside Recording window (not soft-deleted, not retention-expired) → 410 if any expired, with `error_code: "recording.retention_expired"`.
  - Every row has `stream IN ('me', 'counterparty')` → 422 if any has unexpected value.
  - Sum of `byte_size` ≤ `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` → 413 with `error_code: "recording.batch_oversize"`.
- Success: `200 application/zip`, `Content-Disposition: attachment; filename="recordings-YYYYMMDD-HHmmss.zip"`, streaming response. Each WAV stored as `{meeting_title_slug}_{captured_at_iso}_{stream}.wav` (collision-safe via captured_at).
- The zip is built in `zipfile.ZIP_STORED` mode, written directly into the streaming generator; max in-flight memory is ~1 WAV read buffer (~8 MiB default).

### Interface — locale keys (added to BOTH `zh-TW.json` and `en.json`)

```
nav.recordings                                    "錄音檔" / "Recordings"
recordings.list.heading                           "錄音檔" / "Recordings"
recordings.list.subheading                        "保留 30 天內的所有錄音檔" / "All recordings within the 30-day Recording window"
recordings.list.empty                             "目前沒有錄音檔" / "No recordings yet"
recordings.list.empty.expiredHint                 "超過 30 天的錄音檔已依保留政策清除" / "Recordings older than 30 days are removed by the retention policy"
recordings.list.searchPlaceholder                 "搜尋會議名稱" / "Search meeting title"
recordings.list.dateRange.since                   "起" / "From"
recordings.list.dateRange.until                   "迄" / "To"
recordings.list.columns.date                      "錄音時間" / "Captured at"
recordings.list.columns.meeting                   "會議" / "Meeting"
recordings.list.columns.counterparty              "對方" / "Counterparty"
recordings.list.columns.duration                  "時長" / "Duration"
recordings.list.columns.size                      "檔案大小" / "File size"
recordings.list.columns.stream                    "聲道" / "Stream"
recordings.list.streamBadge.me                    "我方" / "Me"
recordings.list.streamBadge.counterparty          "對方" / "Counterparty"
recordings.list.action.download                   "下載" / "Download"
recordings.list.action.batchDownload              "批量下載" / "Batch download"
recordings.list.action.viewMeeting                "前往會議" / "Open meeting"
recordings.list.batch.selectedCount               "已選 {{count}} 筆" / "{{count}} selected"
recordings.list.batch.confirm                     "下載 ZIP" / "Download ZIP"
recordings.list.batch.zipReady                    "ZIP 下載已開始" / "ZIP download started"
errors.recording.batchOversize                    "選取的錄音檔總大小超過 {{limit}}，請減少數量後再試" / "Selected recordings exceed {{limit}}; reduce the selection and retry"
errors.recording.retentionExpired                 "選取的錄音檔中有 {{count}} 筆已超過保留期" / "{{count}} of the selected recordings have passed the Recording window"
```

### Failure modes

- Stale `/calendar/import` bookmark → standard TanStack 404 (no redirect).
- Recording-window expiry mid-flight (race between list response and batch-download): batch endpoint enforces freshness, returns 410. Frontend refreshes list on toast.
- Concurrent retention-job deletion during batch zip stream: stream the zip from rows whose WAV files exist; if a file disappears mid-stream, abort the stream with a trailer error and log. (Rare; surfaces as a truncated zip — accepted trade-off.)
- Auth gateway forwarding `/api/recordings/**` — verify in tasks; existing wildcard forwarder for `/api/**` likely covers it, but verify-not-modify is the rule.

### Acceptance criteria

- `bun --filter @meeting-playbook/web test` passes — including new `routes/recordings/index.test.tsx`, locale-parity test, and adjusted `route-tree` / `routes-i18n` tests.
- `cd packages/backend && uv run pytest` passes — including new tests for `GET /api/recordings` (filter, pagination, auth, retention exclusion, `them` filtering) and `POST /api/recordings/batch-download` (auth, ownership, retention 410, oversize 413, `them` 422, happy-path zip integrity).
- `bun run lint` and `bun run format` clean.
- Manual: visiting `/calendar/import` 404s, visiting `/recordings` works, "Import from calendar" button on `/meetings` lands at `/settings/integrations`.

### Scope boundaries

In scope:
- Route deletion + new route + nav link update.
- New backend endpoints (`GET /api/recordings`, `POST /api/recordings/batch-download`).
- New env var `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` (default 2147483648).
- i18n parity for all new strings.
- Capability spec deltas for `recording-retention`, `meetings-calendar-view`, `settings-shell`.
- New capability spec `recording-index`.

Out of scope:
- Any visual / token / primitive change (P1/P2/P3 own).
- Meeting detail layout (P5).
- Dashboard, Settings sub-nav (A2/A3 = no-op).
- Recording editing, format conversion, sharing, bulk delete.
- Cursor-based pagination, full-text search, queued background download.
- New retention rules.

## Risks / Trade-offs

- [Batch zip OOM with very large selections] → Pre-flight `byte_size` sum + 413 reject; streaming `STORED` zip caps in-flight memory at a single WAV read buffer; configurable cap.
- [Frontend list and batch-download race with retention job mid-window] → Batch endpoint re-checks retention at request time; UI shows a refresh-prompting toast on 410. Inconsistency window is ≤ one polling interval.
- [TanStack route removal breaks bookmarks] → Internal route only, no external dependents. Accepted; documented in proposal.
- [Sidebar nav order is a guess] → Open question, surface to user before merge.
- [ILIKE search scales poorly past 10k rows per user] → Acceptable for current scale; trigram index is a follow-up if needed.
- [Locale parity test enforces sync but doesn't enforce translation quality] → Manual review for zh-TW phrasing of new strings; English-only PR is auto-blocked by the existing `locales.test.ts`.
- [Concurrent retention deletion during zip stream] → Truncated zip on rare race. Logged. Accepted because the alternative (locking) hurts retention job throughput.
- [`them` stream value still in DB somewhere despite CHECK constraint] → Filtered in list, 422 in batch; separate audit change can purge if found.

## Migration Plan

1. Implement backend endpoints + tests behind no flag (no user-facing path yet).
2. Implement frontend `/recordings` route + nav link in same PR (the new route only renders if endpoints exist).
3. Same PR: delete `/calendar/import` route, redirect button on `/meetings`.
4. Locale-parity test gates merge.
5. Deploy together — there is no partial-deploy concern because all three changes (kill calendar route, add recordings route, add backend endpoints) are within a single service boundary per layer.
6. Rollback: revert PR — `/calendar/import` route resurrects, `/recordings` disappears, endpoints 404. No data migration to undo.

## Open Questions

- **Sidebar nav placement**: Meetings → Recordings → Dashboard is my proposal. User to confirm or override.
- **Filename convention inside zip**: `{meeting_title_slug}_{captured_at_iso}_{stream}.wav` proposed. User to confirm.
- **`RECORDING_BATCH_DOWNLOAD_MAX_BYTES` default**: 2 GiB chosen as "covers 30-day window for typical user". User to confirm or override (env var so easy to change post-merge).
- **Auth gateway proxy**: assume the existing `/api/**` wildcard covers `/api/recordings/**` — if it does not, add a route in `packages/auth`. Verified during apply, not in propose.
- **Settings (A3) confirmation**: user wrote "並列就好" — confirmed no-op. Calling it out so the next reviewer doesn't expect work here.
- **Dashboard (A2) confirmation**: user wrote "維持現狀" — confirmed no-op.
