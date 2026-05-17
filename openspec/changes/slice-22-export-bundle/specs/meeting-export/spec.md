## ADDED Requirements

### Requirement: MeetingExportBundler streams a ZIP bundle for a single meeting

The backend SHALL provide `MeetingExportBundler` at `packages/backend/meeting_playbook/export/bundler.py` exporting an async method `iter_zip_chunks(meeting_id: str, user_id: str) -> AsyncIterator[bytes]` that yields ZIP frame bytes lazily. The bundler SHALL assemble the ZIP archive in a `tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024)` so small archives stay in memory and only large bundles spill to disk. The bundler MUST refuse to load any WAV file fully into memory; each WAV SHALL be written into its ZIP entry through `chunked_wav_reader(path, chunk_bytes=1024 * 1024)` which reads the file in 1 MiB chunks via `with path.open("rb") as f: while chunk := f.read(chunk_bytes): yield chunk`. When the meeting does not exist OR exists but is owned by a different `user_id`, the bundler SHALL raise `MeetingNotFound` so the router can surface HTTP 404 with `error_code = meeting.not_found`.

#### Scenario: Bundler yields ZIP bytes incrementally for an owned meeting

- **GIVEN** user `u_a` owns meeting `m_1` with one Playbook row, three TranscriptChunk rows, one Summary row, and two Recording rows whose `deleted_at IS NULL`
- **WHEN** `MeetingExportBundler.iter_zip_chunks("m_1", "u_a")` is iterated to completion
- **THEN** the concatenated bytes SHALL form a valid ZIP archive whose `namelist()` contains exactly `playbook.md`, `transcript.md`, `summary.md`, `recordings/counterparty.wav`, and `recordings/me.wav` in some order

#### Scenario: Bundler refuses to materialize a large WAV in memory

- **GIVEN** a meeting whose single Recording row points at a 200 MiB WAV file on disk and whose `deleted_at IS NULL`
- **WHEN** `MeetingExportBundler.iter_zip_chunks` is fully consumed while `tracemalloc` measures the Python heap delta
- **THEN** the peak Python heap delta attributable to the bundler SHALL remain below 20 MiB, demonstrating chunked streaming rather than a full file load

#### Scenario: Bundler raises MeetingNotFound for a meeting owned by a different user

- **GIVEN** user `u_b` owns meeting `m_2` and user `u_a` does not
- **WHEN** `MeetingExportBundler.iter_zip_chunks("m_2", "u_a")` is iterated
- **THEN** the iterator SHALL raise `MeetingNotFound` before yielding any byte

### Requirement: ZIP bundle excludes recordings whose Recording row is soft-deleted

The bundler SHALL include in `recordings/{stream}.wav` only those Recording rows whose `deleted_at IS NULL`. Recordings whose `deleted_at IS NOT NULL` SHALL be omitted entirely from the ZIP namelist. The exclusion SHALL be implemented at the SQL query layer (`SELECT ... WHERE meeting_id = :meeting_id AND deleted_at IS NULL`) so file-system existence is not consulted as a secondary check. Playbook, transcript, and summary markdown content SHALL remain in the ZIP regardless of whether any Recording row is soft-deleted, because they are not subject to the Recording window.

#### Scenario: Soft-deleted recording is excluded but the other artefacts remain

- **GIVEN** a meeting with two Recording rows where `counterparty` has `deleted_at IS NULL` and `me` has `deleted_at = 2026-03-01T00:00:00Z`, plus a Playbook row, three TranscriptChunk rows, and a Summary row
- **WHEN** the ZIP is generated through the bundler
- **THEN** the ZIP namelist SHALL contain `playbook.md`, `transcript.md`, `summary.md`, and `recordings/counterparty.wav`; it SHALL NOT contain `recordings/me.wav`

#### Scenario: All recordings expired still produces a markdown-only bundle

- **GIVEN** a meeting whose both Recording rows have `deleted_at` set and which still has a Playbook, transcript, and Summary
- **WHEN** the ZIP is generated
- **THEN** the ZIP namelist SHALL contain exactly `playbook.md`, `transcript.md`, and `summary.md` and SHALL NOT contain any entry under the `recordings/` prefix

### Requirement: Bundler skips summary.md when no Summary row exists

The bundler SHALL write `summary.md` to the ZIP only when a Summary row exists for the meeting. Absence of a Summary row SHALL NOT write an empty `summary.md` file and SHALL NOT raise an error. Playbook and transcript markdown SHALL always be written, even when both are empty (the empty case is still a valid Playbook with placeholder text and an empty `# Transcript` body).

#### Scenario: Meeting without a summary omits summary.md

- **GIVEN** a completed meeting with Playbook + TranscriptChunks but no Summary row
- **WHEN** the ZIP is generated
- **THEN** the namelist SHALL contain `playbook.md` and `transcript.md` and SHALL NOT contain `summary.md`

#### Scenario: Meeting with empty Playbook content still writes playbook.md

- **GIVEN** a meeting whose Playbook row has every structured field set to empty string and `free_form_markdown` empty
- **WHEN** the ZIP is generated
- **THEN** the namelist SHALL contain `playbook.md`; the file SHALL contain the H1 meeting title and six empty-placeholder H2 sections (one per Playbook field)

### Requirement: playbook_to_markdown serializes the Playbook into a deterministic structure

The function `playbook_to_markdown(playbook: Playbook, *, meeting_title: str) -> str` at `packages/backend/meeting_playbook/export/markdown.py` SHALL produce a deterministic markdown document with: (1) an H1 of `# {meeting_title}`, (2) the `free_form_markdown` content verbatim when non-empty, followed by a blank line, (3) six H2 sections in the exact order `Objective`, `Counterparty Profile`, `Anticipated Topics`, `Anticipated Objections`, `Talking Points`, `Red Lines`, each followed by the corresponding Playbook field content, (4) for any Playbook field whose value is empty after `.strip()`, the literal placeholder `_(empty)_` SHALL appear as that section's body so consumers can grep for unfilled fields. The function SHALL be a pure function with no I/O.

#### Scenario: Fully populated Playbook emits six H2 sections plus free-form

- **GIVEN** a Playbook with `free_form_markdown = "Note: skip dessert"` and all six fields set to non-empty strings
- **WHEN** `playbook_to_markdown(playbook, meeting_title="Quarterly Review")` runs
- **THEN** the returned string SHALL begin with `# Quarterly Review`, then `Note: skip dessert`, then six `## ` headers in the order `Objective`, `Counterparty Profile`, `Anticipated Topics`, `Anticipated Objections`, `Talking Points`, `Red Lines`, each followed by the matching field content

#### Scenario: Empty Playbook fields render as _(empty)_ placeholder

- **GIVEN** a Playbook whose `objective` is empty and `talking_points` is `"   "` (whitespace only)
- **WHEN** `playbook_to_markdown(...)` runs
- **THEN** the `## Objective` and `## Talking Points` sections SHALL each have `_(empty)_` as their body and the other four sections SHALL render their non-empty content

### Requirement: transcript_to_markdown renders TranscriptChunk rows with speaker label mapping

The function `transcript_to_markdown(chunks: list[TranscriptChunk]) -> str` at `packages/backend/meeting_playbook/export/markdown.py` SHALL produce a markdown document whose first line is `# Transcript` followed by a blank line and then one paragraph per chunk in the input order. Each paragraph SHALL match the pattern `**[HH:MM:SS] {label}**: {text}` where `HH:MM:SS` is `chunk.started_at` formatted as wall-clock time and `label` is derived from `chunk.speaker` via the mapping: `"me" -> "Me (我方)"`, `"counterparty" -> "Counterparty (對方)"`, and `"speaker_cluster_{N}" -> "與會者 {N}"` for any positive integer N. Any other value of `chunk.speaker` SHALL pass through unchanged. The function SHALL be a pure function with no I/O.

#### Scenario: Mixed speakers render with locale-aware labels

- **GIVEN** chunks in order: `(speaker="me", started_at=2026-05-01T10:00:00Z, text="Hi")`, `(speaker="counterparty", started_at=2026-05-01T10:00:05Z, text="Hello")`, `(speaker="speaker_cluster_3", started_at=2026-05-01T10:00:10Z, text="Joining")`
- **WHEN** `transcript_to_markdown(chunks)` runs
- **THEN** the body SHALL contain three lines in order: `**[10:00:00] Me (我方)**: Hi`, `**[10:00:05] Counterparty (對方)**: Hello`, `**[10:00:10] 與會者 3**: Joining`

#### Scenario: Empty chunk list still renders the H1

- **GIVEN** an empty list of TranscriptChunks
- **WHEN** `transcript_to_markdown([])` runs
- **THEN** the returned string SHALL be exactly `# Transcript\n` (H1 header plus single newline, no body paragraphs)

### Requirement: summary_to_markdown passes the existing markdown through under an H1

The function `summary_to_markdown(summary: Summary) -> str` at `packages/backend/meeting_playbook/export/markdown.py` SHALL produce `# Summary\n\n{summary.markdown}\n` verbatim. The function SHALL be a pure function with no I/O. It SHALL NOT be invoked when `summary` is `None` — the bundler is responsible for skipping the call.

#### Scenario: Summary markdown is included unchanged

- **GIVEN** a Summary whose `markdown` field is `"## Decisions\n- Ship Q3 launch.\n"`
- **WHEN** `summary_to_markdown(summary)` runs
- **THEN** the returned string SHALL be `"# Summary\n\n## Decisions\n- Ship Q3 launch.\n\n"` (H1, blank line, body content, trailing newline)

### Requirement: GET /api/meetings/{id}/export streams a ZIP with RFC 5987 Content-Disposition

The backend SHALL expose `GET /api/meetings/{meeting_id}/export` (registered through `packages/backend/meeting_playbook/export/router.py` and included in `server.py`). The endpoint SHALL require the gateway-injected `X-User-Id` header per the auth-gateway contract. On success the endpoint SHALL return HTTP 200 with `Content-Type: application/zip` and a `Content-Disposition` header that uses RFC 5987 encoding for the unicode filename: `attachment; filename="{ascii_slug(title)}__{scheduled_at_date}.zip"; filename*=UTF-8''{percent_encoded_unicode_filename}`. The response body SHALL be a `StreamingResponse` whose iterator is `MeetingExportBundler.iter_zip_chunks(meeting_id, x_user_id)`. When the meeting does not exist or is owned by another user, the endpoint SHALL respond with HTTP 404 and body `{"error_code": "meeting.not_found", "message": "..."}` per the existing meeting-management contract.

The `ascii_slug(title)` helper SHALL keep characters in `[A-Za-z0-9._-]`, replace any other character with `_`, collapse consecutive `_` into one, trim leading and trailing `_`, truncate to 80 characters, and fall back to the literal string `meeting` when the input is empty or trims to empty.

#### Scenario: Owned meeting returns a streaming ZIP with both filename forms

- **GIVEN** an authenticated user `u_a` who owns meeting `m_1` with `title = "Q3 規劃會議"` and `scheduled_at = 2026-05-15T14:00:00Z`
- **WHEN** the user sends `GET /api/meetings/m_1/export` through the gateway (which injects `X-User-Id: u_a`)
- **THEN** the response status SHALL be HTTP 200, `Content-Type` SHALL be `application/zip`, the `Content-Disposition` header SHALL contain BOTH `filename="Q3_______.zip"` (ASCII fallback — chinese chars replaced) prefixed with the date suffix `__2026-05-15` AND `filename*=UTF-8''Q3%20%E8%A6%8F%E5%8A%83%E6%9C%83%E8%AD%B0__2026-05-15.zip`

##### Example: ascii_slug transformations

| Input title | ascii_slug output | Notes |
| ----------- | ----------------- | ----- |
| `"Quarterly Review"` | `Quarterly_Review` | space → `_` |
| `"Q3 規劃會議"` | `Q3` | unicode chars → `_`, trim trailing `_` |
| `"!!!!"` | `meeting` | all replaced + trimmed → empty → fallback |
| `""` | `meeting` | empty input → fallback |
| `"A" * 100` | 80-char `A` string | truncated to 80 |

#### Scenario: Cross-user export returns 404 with meeting.not_found error code

- **GIVEN** user `u_a` is authenticated and meeting `m_2` is owned by user `u_b`
- **WHEN** `u_a` sends `GET /api/meetings/m_2/export`
- **THEN** the response status SHALL be HTTP 404 and the response body SHALL be `{"error_code": "meeting.not_found", "message": "..."}`; the response MUST NOT reveal whether `m_2` exists

#### Scenario: Missing X-User-Id header is rejected per auth-gateway contract

- **GIVEN** a request to `GET /api/meetings/m_1/export` reaching the backend without an `X-User-Id` header
- **WHEN** the backend processes the request
- **THEN** the response SHALL be HTTP 401 with `error_code = auth.gateway_bypass`, matching the auth-gateway contract for all `/api/*` endpoints

### Requirement: Frontend meeting detail exposes an Export button that triggers a browser download

The frontend SHALL render an Export button on the meeting detail route (`packages/web/src/routes/meetings/detail.tsx`) wired to `packages/web/src/components/export-meeting-button.tsx`. The button label SHALL be `t("meetings.detail.export")` which resolves to `匯出` in zh-TW and `Export` in en. Clicking the button SHALL invoke `exportMeeting(meetingId, expectedFilename)` from `packages/web/src/lib/export-api.ts`, which SHALL `fetch('/api/meetings/{id}/export')`, read the response as a `Blob`, create an object URL via `URL.createObjectURL`, programmatically click a hidden `<a download>` element to start the browser download, and revoke the object URL afterwards. While the fetch is in flight the button SHALL be disabled and SHALL display a spinner. Failure responses (HTTP 4xx/5xx with the error envelope) SHALL surface a localized toast via `localizedErrorMessage(error_code, t)`.

#### Scenario: User clicks Export and the browser downloads the ZIP

- **GIVEN** a user is viewing meeting `m_1` and the export endpoint will respond HTTP 200 with a valid ZIP body
- **WHEN** the user clicks the Export button
- **THEN** the button SHALL transition to a disabled spinner state during the fetch, the browser SHALL start downloading a file whose suggested filename matches the server `Content-Disposition`, and the button SHALL return to its enabled label after the download starts

#### Scenario: Export failure surfaces a localized error toast

- **GIVEN** the export endpoint returns HTTP 404 with `{"error_code": "meeting.not_found"}`
- **WHEN** the user clicks the Export button
- **THEN** a toast SHALL appear containing the message resolved by `localizedErrorMessage("meeting.not_found", t)` in the active locale, and the button SHALL return to enabled state

### Requirement: Export i18n strings exist in both locale files

The locale files `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` SHALL each contain matching keys under the `meetings.detail` namespace covering the export feature: `export` (button label), `exporting` (in-flight label), and `exportFailed` (toast prefix for unrecognized errors). The deep-equal test in `packages/web/src/locales/locales.test.ts` SHALL pass after the keys are added in both files.

#### Scenario: Both locale files contain the export key set

- **GIVEN** the post-change repository state
- **WHEN** the locales deep-equal test runs
- **THEN** the test SHALL pass, confirming that `meetings.detail.export`, `meetings.detail.exporting`, and `meetings.detail.exportFailed` exist with string values in both `zh-TW.json` and `en.json`

##### Example: Required key/value pairs

| Key | zh-TW value | en value |
| --- | ----------- | -------- |
| `meetings.detail.export` | `匯出` | `Export` |
| `meetings.detail.exporting` | `匯出中…` | `Exporting…` |
| `meetings.detail.exportFailed` | `匯出失敗` | `Export failed` |
