## MODIFIED Requirements

### Requirement: POST /api/meetings accepts an attachments list that associates pre-uploaded attachments with the new meeting

The endpoint `POST /api/meetings` SHALL accept an optional `attachments` field in the request body containing a JSON array of attachment identifier strings. Each identifier MUST reference a **staged** attachment row uploaded through `POST /api/attachments/staging` (slice-24) that is owned by the authenticated user AND has `meeting_id IS NULL` (i.e., not yet associated with any meeting) AND has `deleted_at IS NULL`. The endpoint SHALL validate every identifier against all three conditions BEFORE creating the meeting row; if any identifier fails validation the endpoint MUST NOT create the meeting and MUST return HTTP 422 with `error_code: attachment.not_attachable`.

When all identifiers pass validation, the endpoint SHALL execute the attach step as part of meeting creation. The attach step SHALL, **inside a single database transaction**:

1. Create the meeting row
2. For each referenced attachment, update its `meeting_id` to the new meeting's id
3. Physically move each attachment file from `ATTACHMENT_DIR/_staging/<user_id>/<att_id><ext>` to `ATTACHMENT_DIR/<new_meeting_id>/<att_id><ext>` and update the row's `file_path` accordingly

The file move SHALL use `os.rename` first (atomic when source and destination share a filesystem) and fall back to `shutil.move` when `os.rename` raises `OSError EXDEV` (cross-filesystem).

If any step in the attach pipeline fails (database error, file system error, or — when `calendar_event_id` is also set — Playbook generation timeout / failure), the endpoint SHALL roll back the partial state: any files already moved out of staging SHALL be moved back to the staging path, every modified row's `meeting_id` SHALL be reset to NULL, and the meeting row (if already inserted) SHALL be removed. The endpoint MUST return the appropriate error code for the underlying failure (e.g., `playbook.generation_timeout` when the Playbook step fails); the rollback is transparent to the client.

#### Scenario: Successful create moves staged files into the meeting directory

- **GIVEN** an authenticated user owns two staged attachments `att_1` and `att_2`, each with `meeting_id = null`, files living under `ATTACHMENT_DIR/_staging/<user>/`
- **WHEN** the user sends `POST /api/meetings` with body containing `attachments: ["att_1", "att_2"]` plus the three required free-text fields
- **THEN** the response SHALL be HTTP 201
- **AND** after the request both `att_1` and `att_2` rows SHALL have `meeting_id` equal to the new meeting's id
- **AND** both files SHALL now live under `ATTACHMENT_DIR/<new_meeting_id>/<att_id><ext>`
- **AND** the original staging paths SHALL no longer exist

#### Scenario: Attachment owned by another user is rejected with attachment.not_attachable

- **GIVEN** user A is authenticated and a staged attachment `att_other` is owned by user B with `meeting_id = null`
- **WHEN** user A sends `POST /api/meetings` with body containing `attachments: ["att_other"]`
- **THEN** the response SHALL be HTTP 422 with `error_code: attachment.not_attachable`
- **AND** no meeting row SHALL be created
- **AND** `att_other`'s `meeting_id` SHALL remain null and its file SHALL remain in user B's staging path

#### Scenario: Already-attached attachment is rejected with attachment.not_attachable

- **GIVEN** an attachment `att_done` owned by the authenticated user with `meeting_id` already pointing to an existing meeting (not null)
- **WHEN** the user sends `POST /api/meetings` with body containing `attachments: ["att_done"]`
- **THEN** the response SHALL be HTTP 422 with `error_code: attachment.not_attachable`
- **AND** no new meeting row SHALL be created

#### Scenario: Generator failure rolls back the attach step

- **GIVEN** the user submits `POST /api/meetings` with `calendar_event_id` non-null and `attachments: ["att_1"]`
- **AND** the Playbook generator raises `PlaybookGenerationTimeout` after the meeting row is inserted and `att_1` has been moved into the meeting directory
- **WHEN** the endpoint processes the failure
- **THEN** the response SHALL surface `error_code: playbook.generation_timeout` (the underlying generator error)
- **AND** `att_1`'s file SHALL be moved back to `ATTACHMENT_DIR/_staging/<user>/<att_1><ext>`
- **AND** `att_1`'s row SHALL have `meeting_id = NULL` again
- **AND** the meeting row created during this request SHALL be removed
