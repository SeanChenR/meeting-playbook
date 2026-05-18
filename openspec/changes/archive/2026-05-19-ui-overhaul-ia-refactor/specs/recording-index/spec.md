## ADDED Requirements

### Requirement: GET /api/recordings lists the current user's recordings within the Recording window

The backend SHALL expose `GET /api/recordings` returning every Recording owned by the authenticated user where `deleted_at IS NULL` AND `captured_at >= NOW() - INTERVAL '{RECORDING_RETENTION_DAYS} days'` AND `stream IN ('me', 'counterparty')`. The endpoint SHALL accept query parameters `since` (ISO date), `until` (ISO date), `search` (string, ILIKE on meeting title), `page` (int, default 1), and `page_size` (int, default 25, max 100). The response body SHALL conform to `{ recordings: RecordingSummary[], total: int, page: int, page_size: int }` where `RecordingSummary` exposes `id`, `meeting_id`, `meeting_title`, `counterparty_label`, `captured_at`, `duration_ms`, `byte_size`, and `stream`.

#### Scenario: list current user recordings ordered by captured_at descending

- **WHEN** an authenticated user calls `GET /api/recordings` with no filters
- **THEN** the system returns 200 with a `recordings` array sorted by `captured_at` descending
- **AND** every returned row belongs to a meeting owned by the user
- **AND** every returned row has `deleted_at IS NULL`
- **AND** every returned row has `captured_at >= NOW() - RECORDING_RETENTION_DAYS`
- **AND** every returned row has `stream` in `('me', 'counterparty')`

#### Scenario: filter by date range

- **WHEN** the user calls `GET /api/recordings?since=2026-05-01&until=2026-05-10`
- **THEN** every returned row has `captured_at` in `[2026-05-01T00:00:00Z, 2026-05-10T23:59:59Z]`
- **AND** rows outside the range are excluded
- **AND** rows older than the Recording window are excluded even if inside the user-supplied range

#### Scenario: search by meeting title via ILIKE

- **WHEN** the user calls `GET /api/recordings?search=Acme`
- **THEN** every returned row's `meeting_title` matches `%Acme%` case-insensitively
- **AND** rows whose meeting title does not match are excluded

#### Scenario: page-based pagination

- **WHEN** the user calls `GET /api/recordings?page=2&page_size=10`
- **THEN** the response includes `page: 2`, `page_size: 10`, and `total` reflecting the unpaginated count
- **AND** the `recordings` array contains at most 10 rows starting from offset 10

#### Scenario: foreign user recordings are not exposed

- **GIVEN** user A owns 3 recordings and user B owns 5 recordings
- **WHEN** user B calls `GET /api/recordings`
- **THEN** the response contains exactly user B's 5 recordings
- **AND** no row owned by user A is present in the response

#### Scenario: legacy 'them' stream values are filtered out

- **GIVEN** a row in the recording table somehow has `stream = 'them'`
- **WHEN** any authenticated user calls `GET /api/recordings`
- **THEN** that row is excluded from the response regardless of ownership

### Requirement: POST /api/recordings/batch-download streams a ZIP of selected recordings with a configurable size cap

The backend SHALL expose `POST /api/recordings/batch-download` accepting a JSON body `{ recording_ids: string[] }` with length between 1 and 200. The endpoint SHALL pre-flight validate (a) every id belongs to the authenticated user, (b) every row is still inside the Recording window and not soft-deleted, (c) every row has `stream IN ('me', 'counterparty')`, and (d) the sum of `byte_size` across selected rows MUST NOT exceed `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` (default 2147483648 bytes / 2 GiB). On success the endpoint SHALL return `200 application/zip` as a streaming response built with `zipfile.ZIP_STORED`, with `Content-Disposition: attachment; filename="recordings-{YYYYMMDD-HHmmss}.zip"`. Each WAV inside the zip SHALL be named `{meeting_title_slug}_{captured_at_iso}_{stream}.wav`.

#### Scenario: happy path returns a streaming zip

- **GIVEN** an authenticated user owns 3 in-window recordings totaling 500 MiB
- **WHEN** the user calls `POST /api/recordings/batch-download` with all 3 ids
- **THEN** the response is 200 with `Content-Type: application/zip`
- **AND** the response is a streaming body
- **AND** the zip contains 3 WAV entries with filenames following `{slug}_{iso}_{stream}.wav`

#### Scenario: foreign id triggers 403

- **GIVEN** user B requests batch-download with an id owned by user A
- **WHEN** the endpoint validates ownership
- **THEN** the response is 403 with `error_code: "recording.forbidden"`
- **AND** no zip is streamed

#### Scenario: any retention-expired id triggers 410

- **GIVEN** the request contains an id whose row is soft-deleted or whose `captured_at` is outside the Recording window
- **WHEN** the endpoint validates retention
- **THEN** the response is 410 with `error_code: "recording.retention_expired"`
- **AND** no zip is streamed

#### Scenario: any 'them' stream value triggers 422

- **GIVEN** the request contains an id whose row has `stream = 'them'`
- **WHEN** the endpoint validates stream channel
- **THEN** the response is 422 with `error_code: "recording.invalid_stream"`
- **AND** no zip is streamed

#### Scenario: oversize selection triggers 413

- **GIVEN** the sum of `byte_size` for requested ids exceeds `RECORDING_BATCH_DOWNLOAD_MAX_BYTES`
- **WHEN** the endpoint runs pre-flight size check
- **THEN** the response is 413 with `error_code: "recording.batch_oversize"`
- **AND** the response body includes the configured limit value

#### Scenario: streaming uses STORED zip mode for bounded memory

- **WHEN** the endpoint builds the zip
- **THEN** entries are added with `zipfile.ZIP_STORED` (no deflate)
- **AND** the FastAPI response uses `StreamingResponse` with a generator
- **AND** the in-flight memory usage stays at roughly one WAV read buffer regardless of total zip size

### Requirement: /recordings route renders the recording index inside the Recording window

The frontend SHALL register an authenticated route `/recordings` rendering a list page of every recording inside the Recording window for the current user, with search, date filter, pagination, single download, and multi-select batch download. The page SHALL read filter state from URL query params (`since`, `until`, `search`, `page`) so it is bookmarkable and back-button friendly.

#### Scenario: authenticated user opens the recordings index

- **WHEN** an authenticated user navigates to `/recordings`
- **THEN** the page calls `GET /api/recordings` with current URL query params
- **AND** renders the returned rows in a table with columns: captured-at, meeting title, counterparty, duration, file size, stream badge

#### Scenario: unauthenticated user is redirected through ProtectedShell

- **WHEN** an unauthenticated user navigates to `/recordings`
- **THEN** the existing `ProtectedShell` auth redirect fires before the page renders

#### Scenario: empty Recording window shows localized empty state

- **WHEN** the user has zero recordings inside the Recording window
- **THEN** the page renders the localized `recordings.list.empty` message
- **AND** displays the localized hint about the 30-day retention policy

#### Scenario: per-row Download triggers existing audio endpoint

- **WHEN** the user clicks Download on a row with `meeting_id=M` and `recording_id=R`
- **THEN** the browser navigates to `GET /api/meetings/M/recordings/R/audio`
- **AND** existing recording-retention 410 handling applies if the row has just expired

#### Scenario: multi-select batch download calls POST endpoint

- **WHEN** the user selects 5 rows and clicks Batch download
- **THEN** the page calls `POST /api/recordings/batch-download` with those 5 ids
- **AND** the resulting ZIP stream is saved to disk by the browser as `recordings-{YYYYMMDD-HHmm}.zip`

#### Scenario: batch oversize surfaces localized toast

- **WHEN** the batch-download response is 413 with `error_code: "recording.batch_oversize"`
- **THEN** the page shows a toast using the i18n key `errors.recording.batchOversize`
- **AND** the toast names the configured size limit

#### Scenario: link to source meeting

- **WHEN** the user clicks the meeting title cell of any row
- **THEN** the page navigates to `/meetings/{meeting_id}` for that row

### Requirement: Recordings nav entry SHALL appear in the protected shell

The frontend protected shell SHALL render a sidebar / top-nav entry labeled per the `nav.recordings` locale key linking to `/recordings`, positioned between the Meetings entry and the Dashboard entry.

#### Scenario: nav entry visible to authenticated user

- **WHEN** an authenticated user views any protected page
- **THEN** the nav shows a Recordings entry between Meetings and Dashboard
- **AND** clicking it navigates to `/recordings`

#### Scenario: nav entry label localized

- **WHEN** the active locale is zh-TW
- **THEN** the nav entry reads "錄音檔"
- **WHEN** the active locale is en
- **THEN** the nav entry reads "Recordings"

### Requirement: All user-visible recording-index strings SHALL exist in both locale files

Every user-visible string introduced for `/recordings` SHALL be added to `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json` at the same path within the same change. The existing locale-parity test (`packages/web/src/locales/locales.test.ts`) SHALL gate CI.

#### Scenario: locale parity test catches missing string

- **GIVEN** a developer adds `recordings.list.heading` to `zh-TW.json` only
- **WHEN** CI runs the locale-parity test
- **THEN** the test fails listing the missing key in `en.json`

#### Scenario: new keys ship in both files

- **WHEN** this change merges
- **THEN** every key listed under the `recordings.*`, `nav.recordings`, `errors.recording.batchOversize`, and `errors.recording.retentionExpired` namespaces exists in both `zh-TW.json` and `en.json`

### Requirement: RECORDING_BATCH_DOWNLOAD_MAX_BYTES env var configures the batch download cap

The backend SHALL read configuration value `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` with default `2147483648` (2 GiB). The value SHALL be the hard upper bound enforced by the batch-download pre-flight check.

#### Scenario: default cap applied when env not set

- **GIVEN** `RECORDING_BATCH_DOWNLOAD_MAX_BYTES` is unset
- **WHEN** the backend boots
- **THEN** the configured cap is 2147483648 bytes

#### Scenario: override via env var

- **GIVEN** `RECORDING_BATCH_DOWNLOAD_MAX_BYTES=5368709120` (5 GiB)
- **WHEN** the backend boots
- **THEN** the configured cap is 5368709120 bytes
- **AND** batch-download requests totaling 4 GiB succeed
- **AND** batch-download requests totaling 6 GiB return 413
