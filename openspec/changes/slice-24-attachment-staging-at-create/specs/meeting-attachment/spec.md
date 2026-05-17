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
- For each dropped file, call `uploadStagedAttachment` and append the
  resulting row to a list rendered above the drop zone
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

#### Scenario: Remove a staged file from the list

- **GIVEN** the user has 2 staged attachments listed
- **WHEN** they click the remove button on the first one
- **THEN** the list re-renders with only the second attachment
- **AND** the backend `DELETE /api/attachments/<first>` was called
- **AND** the next form submission's `attachments[]` does NOT include
  the removed id
