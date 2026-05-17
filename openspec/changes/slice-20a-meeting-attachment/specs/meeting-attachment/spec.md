## ADDED Requirements

### Requirement: meeting_attachment table stores per-meeting attachment metadata

The backend SHALL provide a `meeting_attachment` table with columns `(id UUID PRIMARY KEY, meeting_id UUID NOT NULL, file_path TEXT NOT NULL, kind TEXT NOT NULL, original_name TEXT NOT NULL, bytes INTEGER NOT NULL, uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(), deleted_at TIMESTAMPTZ NULL)`. The `meeting_id` column SHALL reference `meeting.id` with `ON DELETE CASCADE` so deleting a meeting removes its attachments automatically. The `kind` column SHALL be constrained by `CHECK (kind IN ('image','pdf','docx','text','markdown'))`. The `bytes` column SHALL be constrained by `CHECK (bytes > 0)`. The table SHALL have an index on `(meeting_id, deleted_at)` to support the list endpoint. The Alembic migration SHALL be reversible: `up` creates the table, `down` drops it.

#### Scenario: Migration creates table with constraints

- **WHEN** `alembic upgrade head` runs from the prior head revision
- **THEN** the `meeting_attachment` table SHALL exist with all columns and types as specified, the `kind` CHECK constraint SHALL reject any value outside the five allowed strings, the `bytes` CHECK constraint SHALL reject zero or negative values, and the FK to `meeting.id` SHALL cascade on delete

#### Scenario: Migration down drops the table cleanly

- **GIVEN** the database at the new head with one populated `meeting_attachment` row
- **WHEN** `alembic downgrade -1` runs
- **THEN** the `meeting_attachment` table SHALL no longer exist and no other tables SHALL be affected

#### Scenario: Deleting a meeting cascades to its attachments

- **GIVEN** meeting `m_a` with three `meeting_attachment` rows
- **WHEN** the `meeting` row for `m_a` is deleted
- **THEN** all three `meeting_attachment` rows for `m_a` SHALL be removed by the database CASCADE without manual cleanup

### Requirement: Upload validation enforces whitelist, per-meeting file count, and per-meeting byte quota

The backend SHALL validate every attachment upload before persisting the file or row. The validation SHALL reject the upload with HTTP 422 and a specific `error_code` when any of the following conditions are met:

1. The declared `Content-Type` is NOT in the whitelist `{image/jpeg, image/png, image/webp, application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/plain, text/markdown}` AND the file extension is NOT in the whitelist `{.jpg, .jpeg, .png, .webp, .pdf, .docx, .txt, .md, .markdown}` → `error_code = "attachment.unsupported_format"`.
2. The meeting already has 5 or more active (`deleted_at IS NULL`) attachment rows → `error_code = "attachment.too_many"`.
3. The sum of `bytes` across active attachment rows for this meeting PLUS the incoming file's size would exceed `30 * 1024 * 1024` bytes (30 MiB) → `error_code = "attachment.quota_exceeded"`.

When validation passes, the backend SHALL infer `kind` as follows: if `Content-Type` matches the whitelist, use the mapped kind; otherwise fall back to extension lookup. When validation fails, the staged file (if any) SHALL be removed from disk before responding so partial uploads do not accumulate.

#### Scenario: Unsupported format is rejected

- **GIVEN** an authenticated user uploading a file with `Content-Type: image/bmp` and filename `chart.bmp` to a meeting with zero existing attachments
- **WHEN** the request reaches `POST /api/meetings/{meeting_id}/attachments`
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.unsupported_format"`, no row SHALL be written to `meeting_attachment`, and no file SHALL remain on disk under `ATTACHMENT_DIR`

#### Scenario: Sixth attachment is rejected

- **GIVEN** an authenticated user and a meeting that already has 5 active `meeting_attachment` rows totalling 10 MiB
- **WHEN** the user POSTs a sixth valid 1 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.too_many"`, the existing 5 rows SHALL remain unchanged, and no new file SHALL be persisted

#### Scenario: Cumulative byte quota is enforced

- **GIVEN** an authenticated user and a meeting whose active attachments sum to 28 MiB across 3 rows
- **WHEN** the user POSTs a 3 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.quota_exceeded"`, the 3 existing rows SHALL remain unchanged, and the staged 3 MiB file SHALL be removed from disk

#### Scenario: Markdown file with octet-stream Content-Type accepted via extension fallback

- **GIVEN** an authenticated user uploading `notes.md` whose browser-provided `Content-Type` is `application/octet-stream`
- **WHEN** the request reaches the upload endpoint
- **THEN** the backend SHALL infer `kind = "markdown"` from the `.md` extension fallback, persist the file, and return HTTP 200 with `{id, kind: "markdown", original_name: "notes.md", bytes, uploaded_at}`

##### Example: whitelist + kind inference matrix

| Content-Type | Filename | Resulting kind | Accepted? |
|--------------|----------|----------------|-----------|
| `image/jpeg` | `proposal.jpg` | `image` | yes |
| `image/png` | `screenshot.png` | `image` | yes |
| `image/webp` | `chart.webp` | `image` | yes |
| `image/bmp` | `legacy.bmp` | — | no — `attachment.unsupported_format` |
| `application/pdf` | `quote.pdf` | `pdf` | yes |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `contract.docx` | `docx` | yes |
| `application/msword` | `contract.doc` | — | no — `attachment.unsupported_format` (legacy `.doc` excluded) |
| `text/plain` | `agenda.txt` | `text` | yes |
| `text/markdown` | `notes.md` | `markdown` | yes |
| `application/octet-stream` | `notes.md` | `markdown` | yes (extension fallback) |
| `application/octet-stream` | `data.bin` | — | no — `attachment.unsupported_format` |

### Requirement: GET list endpoint returns active attachments for the meeting owner

The backend SHALL expose `GET /api/meetings/{meeting_id}/attachments` returning HTTP 200 with body `{"attachments": [{"id": ..., "kind": ..., "original_name": ..., "bytes": ..., "uploaded_at": ...}, ...]}` ordered by `uploaded_at ASC`. Only rows where `deleted_at IS NULL` SHALL be returned. The endpoint SHALL return HTTP 404 when the `meeting_id` does not exist OR is not owned by the authenticated user; the response body SHALL NOT distinguish between "not found" and "not owned" to avoid leaking ownership.

#### Scenario: Owner lists active attachments

- **GIVEN** user `u_a` who owns meeting `m_a` with 2 active attachments and 1 soft-deleted attachment (`deleted_at` set 2 days ago)
- **WHEN** `u_a` sends `GET /api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 200 with exactly 2 attachment entries in `attachments`, both with `deleted_at IS NULL` semantics (their `deleted_at` is not returned in the body)

#### Scenario: Non-owner receives 404

- **GIVEN** user `u_b` who does NOT own meeting `m_a`
- **WHEN** `u_b` sends `GET /api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 404 and the body SHALL NOT confirm or deny the existence of `m_a`

### Requirement: POST upload endpoint persists file and row on success

The backend SHALL expose `POST /api/meetings/{meeting_id}/attachments` accepting `multipart/form-data` with a single field `file`. On a validation-passing upload the endpoint SHALL: (a) persist the file under `ATTACHMENT_DIR/{meeting_id}/{attachment_id}.<canonical_extension>` where `canonical_extension` is determined by the inferred `kind`; (b) insert a `meeting_attachment` row with `(id, meeting_id, file_path, kind, original_name=<browser-provided name>, bytes=<actual bytes written>, uploaded_at=now())`; (c) return HTTP 200 with body `{"id", "kind", "original_name", "bytes", "uploaded_at"}`. The endpoint SHALL return HTTP 404 when the `meeting_id` does not exist or is not owned by the authenticated user.

#### Scenario: Owner uploads a valid PDF successfully

- **GIVEN** an authenticated owner `u_a` of meeting `m_a` with zero existing attachments, and a 2 MiB PDF named `proposal.pdf`
- **WHEN** `u_a` POSTs the file to `/api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 200 with `kind = "pdf"`, `original_name = "proposal.pdf"`, `bytes = 2097152`, and `uploaded_at` populated; a row SHALL exist in `meeting_attachment` with the matching `id`; a file SHALL exist at `ATTACHMENT_DIR/m_a/<id>.pdf` whose byte count equals `bytes`

#### Scenario: Upload to non-owned meeting returns 404

- **GIVEN** an authenticated user `u_b` who does not own meeting `m_a`
- **WHEN** `u_b` POSTs a valid PDF to `/api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 404, no row SHALL be inserted, and no file SHALL be written to disk

### Requirement: DELETE endpoint soft-deletes the row and unlinks the file

The backend SHALL expose `DELETE /api/meetings/{meeting_id}/attachments/{attachment_id}` that sets `deleted_at = now()` on the matching row and calls `Path(file_path).unlink(missing_ok=True)` to remove the file. The endpoint SHALL return HTTP 204 with empty body. The endpoint SHALL return HTTP 404 when the attachment does not exist, does not belong to the meeting, or the meeting is not owned by the authenticated user. Subsequent `GET list` calls SHALL NOT return the deleted attachment.

#### Scenario: Owner deletes an active attachment

- **GIVEN** an authenticated owner of meeting `m_a` and an attachment `a_x` whose `deleted_at IS NULL` and whose file exists on disk
- **WHEN** the owner sends `DELETE /api/meetings/m_a/attachments/a_x`
- **THEN** the response SHALL be HTTP 204, the row's `deleted_at` SHALL be populated, the file SHALL be removed from disk, and a subsequent `GET /api/meetings/m_a/attachments` SHALL NOT include `a_x`

#### Scenario: Delete of already-deleted attachment returns 404

- **GIVEN** an attachment `a_x` whose `deleted_at` was set 1 day ago
- **WHEN** the owner sends `DELETE /api/meetings/m_a/attachments/a_x`
- **THEN** the response SHALL be HTTP 404 (the repository treats soft-deleted rows as not found from the API perspective)

### Requirement: Download endpoint streams the file with original filename

The backend SHALL expose `GET /api/meetings/{meeting_id}/attachments/{attachment_id}/download` that returns the raw file bytes with `Content-Disposition: attachment; filename="<original_name>"` and a `Content-Type` matching the row's `kind`. The endpoint SHALL return HTTP 404 when the attachment does not exist, does not belong to the meeting, is soft-deleted, or the meeting is not owned by the authenticated user. The endpoint SHALL return HTTP 410 with `error_code = "attachment.expired"` when the row exists with `deleted_at IS NULL` but the underlying file is missing from disk (retention cleanup has run between row read and file open).

#### Scenario: Owner downloads an active attachment

- **GIVEN** an authenticated owner of meeting `m_a` and an active attachment `a_x` whose `original_name = "quote.pdf"` and whose file is present on disk
- **WHEN** the owner sends `GET /api/meetings/m_a/attachments/a_x/download`
- **THEN** the response SHALL be HTTP 200 with `Content-Disposition: attachment; filename="quote.pdf"`, `Content-Type: application/pdf`, and a body whose byte count equals the row's `bytes` column

#### Scenario: Download after disk file has gone missing returns 410

- **GIVEN** an attachment row whose `deleted_at IS NULL` but whose `file_path` no longer exists on disk
- **WHEN** the owner sends the download request
- **THEN** the response SHALL be HTTP 410 with body `{error_code: "attachment.expired", message: ...}`

### Requirement: AttachmentDropzone component renders list, dropzone, and progress

The frontend SHALL ship a component `<AttachmentDropzone>` at `packages/web/src/components/attachment-dropzone.tsx` that the meeting detail page renders below the Playbook pane in a collapsible section. The component SHALL display: (a) a list of existing active attachments showing a `kind`-appropriate icon, the `original_name`, formatted `bytes` (e.g., "2.1 MB"), formatted `uploaded_at`, a download button, and a delete button; (b) a drag-drop region that accepts the whitelist mime types and shows the hint "最多 5 個檔案、30MB 上限" / "Max 5 files, 30MB total"; (c) a per-file upload progress indicator driven by `XMLHttpRequest.upload.onprogress`; (d) localized error rendering via `localizedErrorMessage(errorCode, t)` when the backend returns HTTP 422 or 410. All visible strings SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`.

#### Scenario: Dropping a file shows progress and adds to list on success

- **GIVEN** a meeting detail page mounted with zero existing attachments and the backend stubbed to respond HTTP 200 with `{id: "a_1", kind: "pdf", original_name: "proposal.pdf", bytes: 2097152, uploaded_at: "2026-05-15T12:00:00Z"}`
- **WHEN** the user drops a valid 2 MiB PDF onto the dropzone
- **THEN** the component SHALL display an upload progress card transitioning from 0% to 100%; on completion the card SHALL be removed AND a new attachment row SHALL appear in the list with the PDF icon, `original_name = "proposal.pdf"`, and `bytes = "2.0 MB"` (or "2.1 MB" with the project's standard rounding)

#### Scenario: Quota exceeded surfaces localized error

- **GIVEN** the backend stubbed to respond HTTP 422 with `{error_code: "attachment.quota_exceeded", message: ...}`
- **WHEN** the user attempts to upload a file
- **THEN** the component SHALL render the localized message for `attachment.quota_exceeded` (resolved via `localizedErrorMessage`), the progress card SHALL be removed, and the existing attachment list SHALL remain unchanged

#### Scenario: Delete button removes the row after confirmation

- **GIVEN** an attachment shown in the list and the backend stubbed to respond HTTP 204 on DELETE
- **WHEN** the user clicks the delete button for that attachment
- **THEN** the component SHALL POST the DELETE request and on 204 SHALL remove that attachment from the list without a page reload
