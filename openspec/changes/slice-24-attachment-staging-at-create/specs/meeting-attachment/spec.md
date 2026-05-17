## ADDED Requirements

### Requirement: meeting_attachment row supports staged (orphan) state

The `meeting_attachment` table SHALL allow rows with `meeting_id IS NULL`,
representing an attachment uploaded by a user but not yet bound to a
meeting. Such rows are referred to as **staged**.

To preserve ownership when `meeting_id IS NULL`, the table SHALL carry a
`user_id TEXT NOT NULL` column with a foreign key to `user.id`. The
existing FK from `meeting_id` to `meeting.id` remains `ON DELETE CASCADE`
for the attached case.

Staged rows are sweep-eligible by the existing retention job after
`STAGED_ATTACHMENT_TTL_HOURS` (default 24) have elapsed since
`uploaded_at`.

#### Scenario: Staged row exists with NULL meeting_id and explicit user_id

- **GIVEN** a user uploads a file to the staging endpoint
- **WHEN** the upload succeeds
- **THEN** a row in `meeting_attachment` is created with
  `meeting_id = NULL`, `user_id = <the uploader's id>`, `deleted_at = NULL`,
  and `file_path` pointing under `ATTACHMENT_DIR/_staging/<user_id>/`

#### Scenario: Attached row carries user_id mirroring its meeting's owner

- **GIVEN** a row whose `meeting_id` is non-null
- **THEN** that row's `user_id` SHALL equal the `user_id` of the meeting
  named by `meeting_id`

### Requirement: POST /api/attachments/staging uploads to user-scoped staging path

`POST /api/attachments/staging` SHALL accept a multipart `file` field,
validate it against the existing per-meeting whitelist (image/jpeg,
image/png, image/webp, application/pdf, application/vnd.openxml...docx,
text/plain, text/markdown), and persist the file under
`ATTACHMENT_DIR/_staging/<user_id>/<attachment_id><ext>`.

The endpoint SHALL respond HTTP 201 with the same `Attachment` JSON shape
returned by the existing per-meeting upload endpoint, where `meeting_id`
is omitted (or null) and all other fields populated from the new row.

The endpoint SHALL enforce a **per-user staging quota** before persisting:

- Total staged file count (`meeting_id IS NULL AND deleted_at IS NULL AND
  user_id = current`) MUST be less than 10 before this upload
- Total staged bytes for the same set MUST be less than 60 MiB before
  this upload

Quota violations SHALL respond HTTP 422 with error_code
`attachment.staging_quota_exceeded`.

#### Scenario: Successful staged upload returns 201 with attachment payload

- **GIVEN** the user has 0 staged attachments
- **WHEN** they POST a 5 MiB PDF to `/api/attachments/staging`
- **THEN** the response is HTTP 201 with body matching the `Attachment`
  shape (`id`, `kind`, `original_name`, `bytes`, `uploaded_at`)
- **AND** the file exists on disk under
  `ATTACHMENT_DIR/_staging/<user_id>/<att_id>.pdf`
- **AND** a row exists in `meeting_attachment` with `meeting_id = NULL`
  and `user_id = <user>`

#### Scenario: Eleventh staged file is rejected

- **GIVEN** the user already has 10 active staged attachments
- **WHEN** they POST another file to `/api/attachments/staging`
- **THEN** the response is HTTP 422 with body
  `{"error_code": "attachment.staging_quota_exceeded", "message": ...}`
- **AND** no row is created and no file is written

#### Scenario: Staged bytes exceeding 60 MiB rejects the upload

- **GIVEN** the user's existing staged attachments total 58 MiB
- **WHEN** they POST a 5 MiB file
- **THEN** the response is HTTP 422 with error_code
  `attachment.staging_quota_exceeded`

#### Scenario: Disallowed MIME type rejects the upload

- **GIVEN** the user is within staging quota
- **WHEN** they POST a `.zip` file
- **THEN** the response is HTTP 422 with error_code
  `attachment.unsupported_format` (same code as per-meeting upload)

### Requirement: GET /api/attachments?status=pending lists the user's staged attachments

`GET /api/attachments?status=pending` SHALL return HTTP 200 with body
`{"attachments": [Attachment, ...]}` containing every row where
`user_id = <current user>`, `meeting_id IS NULL`, and
`deleted_at IS NULL`. The list SHALL be sorted by `uploaded_at` ascending
so the UI renders them in upload order.

If `status` query is absent or any value other than `"pending"`, the
endpoint SHALL respond HTTP 422 with error_code
`attachment.invalid_status_filter`.

#### Scenario: Lists only the caller's staged rows

- **GIVEN** user A has 2 staged attachments and user B has 1 staged
  attachment
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array has length 2
- **AND** none of the entries belong to user B

#### Scenario: Already-attached rows are excluded

- **GIVEN** user A has 1 staged row and 3 rows attached to existing
  meetings
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array has length 1
- **AND** the entry's `id` matches the staged row

#### Scenario: Soft-deleted rows are excluded

- **GIVEN** user A has 1 staged row with `deleted_at` set to the past
  (soft-deleted)
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array is empty

### Requirement: DELETE /api/attachments/{id} removes a staged row only

`DELETE /api/attachments/{attachment_id}` SHALL accept ids of rows where
`meeting_id IS NULL` AND `user_id = <current user>` AND `deleted_at IS NULL`.
On success it SHALL unlink the file on disk and set `deleted_at` on the
row, then respond HTTP 204.

For ids that match an attached row (`meeting_id IS NOT NULL`), the
endpoint SHALL respond HTTP 404 with error_code `attachment.not_found` —
the caller MUST use the per-meeting delete endpoint instead. Cross-user
ids SHALL also return 404 to avoid information leak.

#### Scenario: Delete staged row succeeds with 204

- **GIVEN** a staged row owned by the caller
- **WHEN** they DELETE `/api/attachments/<id>`
- **THEN** the response is HTTP 204
- **AND** the row's `deleted_at` is now set
- **AND** the file at `ATTACHMENT_DIR/_staging/<user>/<id>.*` is removed

#### Scenario: Delete attached row returns 404

- **GIVEN** an attached row (`meeting_id IS NOT NULL`) owned by the caller
- **WHEN** they DELETE `/api/attachments/<id>` (top-level, not the
  per-meeting endpoint)
- **THEN** the response is HTTP 404 with error_code `attachment.not_found`
- **AND** the row is unchanged

#### Scenario: Cross-user staged row returns 404

- **GIVEN** a staged row owned by user B
- **WHEN** user A calls DELETE `/api/attachments/<that_id>`
- **THEN** the response is HTTP 404 with error_code `attachment.not_found`

### Requirement: Retention job sweeps staged attachments older than the TTL

The existing `RecordingRetentionJob.cleanup` job SHALL, on each scheduled
run, additionally delete rows where:

- `meeting_id IS NULL`
- `deleted_at IS NULL`
- `uploaded_at < now() - STAGED_ATTACHMENT_TTL_HOURS hours`

For each such row, the job SHALL unlink the file at the row's `file_path`
(best-effort — `OSError` is logged and ignored), then hard-DELETE the row
(not soft-delete; staged rows are throwaway).

The 30-day soft-delete sweep for attached rows is unchanged.

#### Scenario: Staged row older than TTL is deleted

- **GIVEN** a staged row with `uploaded_at` = 25 hours ago and
  `STAGED_ATTACHMENT_TTL_HOURS = 24`
- **WHEN** `RecordingRetentionJob.cleanup` runs
- **THEN** the row is removed from `meeting_attachment`
- **AND** the on-disk file is unlinked

#### Scenario: Staged row younger than TTL is kept

- **GIVEN** a staged row with `uploaded_at` = 1 hour ago and
  `STAGED_ATTACHMENT_TTL_HOURS = 24`
- **WHEN** the cleanup job runs
- **THEN** the row is still present
- **AND** the file is still on disk

### Requirement: Frontend StagedAttachmentDropzone uploads to staging and lists current staged

The web UI SHALL provide a `<StagedAttachmentDropzone>` component that
the `/meetings/new` route mounts. The component SHALL:

- Render a drag-drop zone that accepts the same MIME whitelist as the
  per-meeting dropzone
- Accept **multi-file selection** via both drag-drop (a `DataTransfer.files`
  FileList) and the file picker (the underlying `<input type="file">`
  carries the `multiple` attribute). For each accepted file the component
  SHALL call `uploadStagedAttachment` sequentially (one POST completes
  before the next starts) and append each resulting row to the list
- Apply **client-side quota truncation** before issuing any POST using a
  **skip-and-continue (accept-what-fits) algorithm**: iterate the dropped
  files in drop order, maintaining a running staged count and byte sum
  (initialized from the current staged list). For each file, accept it
  if AND only if `running_count + 1 <= 10` AND
  `running_bytes + file.size <= 60 * 1024 * 1024`; otherwise skip that
  file (count it toward `dropped`) and continue to the next. The skip
  rule SHALL NOT short-circuit — a large file that would overflow does
  not block smaller subsequent files that still fit. When `dropped > 0`,
  render an inline warning (`attachment.staging_batch_truncated`)
  naming `dropped` and `accepted` counts. Backend per-file enforcement
  of the quota remains the source of truth — truncation is a UX
  optimization, not a security boundary
- Render a **quota counter** of the shape `<used>/10 個 · <bytesUsed>/60 MiB`
  derived from the current staged list. Counter SHALL update reactively
  whenever the staged list changes
- When `current_staged_count === 10` OR
  `current_staged_bytes >= 60 * 1024 * 1024`, the drop area AND the
  upload button SHALL be `disabled`, and an at-limit hint
  (`staging.at_limit`) SHALL render in place of the empty-state text
- For each listed staged attachment, render a "remove" button that calls
  `deleteStagedAttachment` and removes the row from the list
- Show upload progress (0..100%) per file while a POST is in flight
- Localize backend error codes (`attachment.staging_quota_exceeded`,
  `attachment.unsupported_format`, etc.) via `localizedErrorMessage`

When the user clicks "建立" on `/meetings/new`, the submit handler SHALL
include the ids of every currently-listed staged attachment in the
`POST /api/meetings` request's `attachments[]` field.

#### Scenario: Drop one PDF, see it in the list

- **GIVEN** the user is on `/meetings/new` with the dropzone mounted and
  no staged attachments
- **WHEN** they drop a 2 MiB PDF onto the dropzone
- **THEN** the list above the dropzone renders one row showing the
  filename and size
- **AND** the staged attachment is included in the next form submission's
  `attachments[]`

#### Scenario: Drop three files at once uploads all three sequentially

- **GIVEN** the user has 0 staged attachments and the counter reads `0/10`
- **WHEN** they drop three files (1 MiB PDF, 2 MiB PNG, 3 MiB PDF) onto
  the dropzone in one drag operation
- **THEN** three sequential `POST /api/attachments/staging` requests are
  issued (next starts after the previous resolves)
- **AND** the list renders three rows in upload order
- **AND** the counter advances `0/10 → 1/10 → 2/10 → 3/10` and
  `0/60 MiB → 1/60 MiB → 3/60 MiB → 6/60 MiB`
- **AND** the submit handler's `attachments[]` contains all three ids

#### Scenario: Drop files that would exceed the file-count quota are truncated

- **GIVEN** the user has 8 staged attachments and the counter reads `8/10`
- **WHEN** they drop 5 files onto the dropzone
- **THEN** only the first 2 files are uploaded (one sequential POST each)
- **AND** an inline warning renders with `error_code:
  staging.batch_truncated`, message naming `dropped: 5, accepted: 2`
- **AND** the remaining 3 files are NOT sent to the backend
- **AND** the counter ends at `10/10`

#### Scenario: Drop files that would exceed the byte quota are truncated

- **GIVEN** the user has 1 staged file totalling 58 MiB
  (counter: `1/10 · 58/60 MiB`)
- **WHEN** they drop a 3 MiB file and a 1 MiB file in one operation
- **THEN** only the 1 MiB file is uploaded (the 3 MiB file would push
  total to 61 MiB)
- **AND** the inline warning renders with `staging.batch_truncated`
  naming `dropped: 2, accepted: 1`

#### Scenario: At-limit state disables the dropzone

- **GIVEN** the user has 10 staged attachments
- **WHEN** the dropzone renders
- **THEN** the drop area's `disabled` attribute is true (drag-over does
  not light up)
- **AND** the upload button is `disabled`
- **AND** the empty-state text is replaced with the at-limit hint
  (`staging.at_limit`)
- **AND** the counter reads `10/10`

#### Scenario: Removing a staged row re-enables the dropzone

- **GIVEN** the user has 10 staged attachments and the dropzone is in
  the at-limit state
- **WHEN** they click the remove button on one staged row
- **THEN** the counter drops to `9/10`
- **AND** the drop area is no longer `disabled`
- **AND** the at-limit hint is replaced with the empty-state / normal text

#### Scenario: Remove a staged file from the list

- **GIVEN** the user has 2 staged attachments listed
- **WHEN** they click the remove button on the first one
- **THEN** the list re-renders with only the second attachment
- **AND** the backend `DELETE /api/attachments/<first>` was called
- **AND** the next form submission's `attachments[]` does NOT include
  the removed id

## MODIFIED Requirements

### Requirement: Upload validation enforces whitelist, per-meeting file count, and per-meeting byte quota

The backend SHALL validate every attachment upload before persisting the file or row. The validation SHALL reject the upload with HTTP 422 and a specific `error_code` when any of the following conditions are met:

1. The declared `Content-Type` is NOT in the whitelist `{image/jpeg, image/png, image/webp, application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/plain, text/markdown}` AND the file extension is NOT in the whitelist `{.jpg, .jpeg, .png, .webp, .pdf, .docx, .txt, .md, .markdown}` → `error_code = "attachment.unsupported_format"`.
2. The meeting already has 10 or more active (`deleted_at IS NULL`) attachment rows → `error_code = "attachment.too_many"`.
3. The sum of `bytes` across active attachment rows for this meeting PLUS the incoming file's size would exceed `60 * 1024 * 1024` bytes (60 MiB) → `error_code = "attachment.quota_exceeded"`.

When validation passes, the backend SHALL infer `kind` as follows: if `Content-Type` matches the whitelist, use the mapped kind; otherwise fall back to extension lookup. When validation fails, the staged file (if any) SHALL be removed from disk before responding so partial uploads do not accumulate.

Rationale for the file count and byte limits: per `meeting-attachment` design D12, the per-meeting limits are aligned with the per-user staging limits (10 files / 60 MiB). Aligning the two surfaces means a user's mental model of "what fits" is the same in `/meetings/new` and on the meeting detail page.

#### Scenario: Unsupported format is rejected

- **GIVEN** an authenticated user uploading a file with `Content-Type: image/bmp` and filename `chart.bmp` to a meeting with zero existing attachments
- **WHEN** the request reaches `POST /api/meetings/{meeting_id}/attachments`
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.unsupported_format"`, no row SHALL be written to `meeting_attachment`, and no file SHALL remain on disk under `ATTACHMENT_DIR`

#### Scenario: Eleventh attachment is rejected

- **GIVEN** an authenticated user and a meeting that already has 10 active `meeting_attachment` rows totalling 10 MiB
- **WHEN** the user POSTs an eleventh valid 1 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.too_many"`, the existing 10 rows SHALL remain unchanged, and no new file SHALL be persisted

#### Scenario: Cumulative byte quota is enforced

- **GIVEN** an authenticated user and a meeting whose active attachments sum to 58 MiB across 3 rows
- **WHEN** the user POSTs a 3 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.quota_exceeded"`, the 3 existing rows SHALL remain unchanged, and the staged 3 MiB file SHALL be removed from disk

#### Scenario: Markdown file with octet-stream Content-Type accepted via extension fallback

- **GIVEN** an authenticated user uploading `notes.md` whose browser-provided `Content-Type` is `application/octet-stream`
- **WHEN** the request reaches the upload endpoint
- **THEN** the backend SHALL infer `kind = "markdown"` from the `.md` extension fallback, persist the file, and return HTTP 200 with `{id, kind: "markdown", original_name: "notes.md", bytes, uploaded_at}`

### Requirement: AttachmentDropzone component renders list, dropzone, and progress

The frontend SHALL ship a component `<AttachmentDropzone>` at `packages/web/src/components/attachment-dropzone.tsx` that the meeting detail page renders below the Playbook pane in a collapsible section. The component SHALL display: (a) a list of existing active attachments showing a `kind`-appropriate icon, the `original_name`, formatted `bytes` (e.g., "2.1 MB"), formatted `uploaded_at`, a download button, and a delete button; (b) a drag-drop region that accepts the whitelist mime types and shows the hint "最多 10 個檔案、60 MiB 上限" / "Max 10 files, 60 MiB total"; (c) a per-file upload progress indicator driven by `XMLHttpRequest.upload.onprogress`; (d) localized error rendering via `localizedErrorMessage(errorCode, t)` when the backend returns HTTP 422 or 410. All visible strings SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`.

#### Scenario: Dropping a file shows progress and adds to list on success

- **GIVEN** a meeting detail page mounted with zero existing attachments and the backend stubbed to respond HTTP 200 with `{id: "a_1", kind: "pdf", original_name: "proposal.pdf", bytes: 2097152, uploaded_at: "2026-05-15T12:00:00Z"}`
- **WHEN** the user drops a valid 2 MiB PDF onto the dropzone
- **THEN** the component SHALL display an upload progress card transitioning from 0% to 100%; on completion the card SHALL be removed AND a new attachment row SHALL appear in the list with the PDF icon, `original_name = "proposal.pdf"`, and `bytes = "2.0 MB"` (or "2.1 MB" with the project's standard rounding)
