## ADDED Requirements

### Requirement: `playbook` row SHALL carry the immediately preceding generated version

The `playbook` table SHALL hold three nullable columns —
`previous_free_form_markdown`, `previous_updated_at`, and
`previous_attachment_hash_snapshot` — that together preserve the version
that was active immediately before the most recent `regenerate` call.

These columns SHALL be NULL until the first `regenerate` runs against
that row. After a regenerate, they SHALL contain exactly the values that
the same columns (minus the `previous_` prefix) held one moment earlier
in the same row.

User-save upserts SHALL NOT alter the `previous_*` columns — only the
regenerate flow and the explicit `discard_previous` / `restore_previous`
endpoints SHALL touch them.

#### Scenario: First-ever regenerate captures the prior AI draft

- **GIVEN** a `playbook` row with `free_form_markdown = "draft v1"`,
  `attachment_hash_snapshot = "hash-A"`, and `previous_*` columns all NULL
- **WHEN** the regenerate endpoint completes successfully and writes
  `free_form_markdown = "draft v2"`, `attachment_hash_snapshot = "hash-B"`
- **THEN** the same row's `previous_free_form_markdown` equals `"draft v1"`
- **AND** `previous_attachment_hash_snapshot` equals `"hash-A"`
- **AND** `previous_updated_at` equals the `updated_at` value that the row
  held immediately before the regenerate

#### Scenario: Repeated regenerates only keep the most recent prior version

- **GIVEN** a row whose `free_form_markdown` has been regenerated twice:
  v1 → v2 → v3
- **WHEN** the second regenerate (v2 → v3) completes
- **THEN** `previous_free_form_markdown` equals `"v2"` (not `"v1"`)

#### Scenario: User save leaves snapshot untouched

- **GIVEN** a row where `free_form_markdown = "v2"` and
  `previous_free_form_markdown = "v1"`
- **WHEN** a user-save `upsert_for_meeting` writes
  `free_form_markdown = "v2-edited"`
- **THEN** `previous_free_form_markdown` is still `"v1"`
- **AND** `previous_updated_at` is unchanged

### Requirement: GET / `PlaybookRead` response SHALL expose the previous-version columns

The `PlaybookRead` Pydantic schema SHALL include three fields:

- `previous_free_form_markdown: str | None`
- `previous_updated_at: datetime | None`
- `has_previous_version: bool` (derived: `previous_free_form_markdown is not None`)

`GET /api/meetings/{meeting_id}/playbook` SHALL return all three fields
on every response so the frontend can decide whether to render the diff
mode and compute the diff client-side.

#### Scenario: Row without snapshot returns null previous fields

- **GIVEN** a freshly-created playbook row (no regenerate has happened)
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes `"previous_free_form_markdown": null`,
  `"previous_updated_at": null`, and `"has_previous_version": false`

#### Scenario: Row with snapshot returns full previous fields

- **GIVEN** a row whose `previous_free_form_markdown = "draft v1"` and
  `previous_updated_at = "2026-05-17T10:00:00+00:00"`
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes `"previous_free_form_markdown": "draft v1"`,
  `"previous_updated_at": "2026-05-17T10:00:00+00:00"`, and
  `"has_previous_version": true`

### Requirement: `POST .../playbook/discard_previous` SHALL clear the snapshot without changing the current draft

The endpoint at `POST /api/meetings/{meeting_id}/playbook/discard_previous`
SHALL set all three `previous_*` columns to NULL and leave every other
column unchanged. The response SHALL be HTTP 200 with the updated
`PlaybookRead`.

If `previous_free_form_markdown` is already NULL when the request
arrives, the endpoint SHALL respond with HTTP 404 and error_code
`playbook.no_previous_version`.

#### Scenario: Discard with snapshot present clears it

- **GIVEN** a row where `free_form_markdown = "v2"`,
  `previous_free_form_markdown = "v1"`
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/discard_previous`
  is called by the meeting owner
- **THEN** the response is HTTP 200
- **AND** the response body's `free_form_markdown` is `"v2"`
- **AND** the response body's `has_previous_version` is `false`
- **AND** the row in the database now has all `previous_*` columns equal to NULL

#### Scenario: Discard without snapshot returns 404

- **GIVEN** a row where `previous_free_form_markdown IS NULL`
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/discard_previous`
  is called
- **THEN** the response is HTTP 404
- **AND** the response body's `error_code` equals `playbook.no_previous_version`

#### Scenario: Discard against another user's meeting returns 404

- **GIVEN** a playbook owned by user A
- **WHEN** user B calls `POST /api/meetings/{a_meeting_id}/playbook/discard_previous`
- **THEN** the response is HTTP 404 with `meeting.not_found` (existing
  meeting-ownership scoping rule applies before the snapshot check)

### Requirement: `POST .../playbook/restore_previous` SHALL swap the snapshot back into the current draft

The endpoint at `POST /api/meetings/{meeting_id}/playbook/restore_previous`
SHALL atomically:

- Write `previous_free_form_markdown` into `free_form_markdown`
- Write `previous_attachment_hash_snapshot` into `attachment_hash_snapshot`
- Set all three `previous_*` columns to NULL
- Bump `updated_at` to the request timestamp

The 6 structured fields (`objective`, `counterparty_profile`,
`anticipated_topics`, `anticipated_objections`, `talking_points`,
`red_lines`) SHALL be unchanged because S23 does not snapshot them.

The response SHALL be HTTP 200 with the updated `PlaybookRead`.

If `previous_free_form_markdown` is NULL when the request arrives, the
endpoint SHALL respond with HTTP 404 and error_code
`playbook.no_previous_version`.

#### Scenario: Restore with snapshot present swaps it in

- **GIVEN** a row where `free_form_markdown = "v2"`,
  `attachment_hash_snapshot = "hash-B"`, `previous_free_form_markdown = "v1"`,
  `previous_attachment_hash_snapshot = "hash-A"`
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/restore_previous`
  is called
- **THEN** the response is HTTP 200
- **AND** the response body's `free_form_markdown` is `"v1"`
- **AND** the response body's `attachment_hash_snapshot` is `"hash-A"`
- **AND** the response body's `has_previous_version` is `false`
- **AND** the database row reflects the same values

#### Scenario: Restore without snapshot returns 404

- **GIVEN** a row where `previous_free_form_markdown IS NULL`
- **WHEN** `POST /api/meetings/{meeting_id}/playbook/restore_previous`
  is called
- **THEN** the response is HTTP 404 with error_code `playbook.no_previous_version`

### Requirement: Frontend Playbook pane SHALL expose a `diff` mode in addition to `edit` and `preview`

The playbook pane on `/meetings/{id}` SHALL render a third mode named
`diff` alongside the existing `edit` and `preview` modes. The toggle
button for `diff` mode SHALL only appear when
`has_previous_version === true`.

In `diff` mode the pane SHALL render a line-level visual diff between
`previous_free_form_markdown` and `free_form_markdown` using the
`<PlaybookDiffViewer>` component, plus three action controls:

- "Accept all new" — call `discard_previous`, swap pane back to `edit`
- "Restore all previous" — call `restore_previous`, swap pane back to `edit`
- "Apply cherry-pick" — POST the user-merged markdown via the existing
  user-save upsert, then call `discard_previous`

When the regenerate mutation succeeds AND
`current.free_form_markdown !== previous_free_form_markdown`, the pane
SHALL automatically switch to `diff` mode so the user sees the
comparison without hunting for the toggle.

#### Scenario: Diff toggle hidden when no snapshot exists

- **GIVEN** a playbook detail page mounted for a row where
  `has_previous_version === false`
- **WHEN** the pane renders
- **THEN** the toggle group SHALL contain `edit` and `preview` buttons
  only — no `diff` button

#### Scenario: Diff toggle visible when snapshot exists

- **GIVEN** a playbook detail page mounted for a row where
  `has_previous_version === true`
- **WHEN** the pane renders
- **THEN** the toggle group SHALL contain three buttons: `edit`, `preview`, `diff`

#### Scenario: Regenerate auto-switches to diff mode

- **GIVEN** the pane is on `edit` mode and the regenerate mutation is
  in flight
- **WHEN** the mutation resolves with `current.free_form_markdown` 
  different from `previous_free_form_markdown`
- **THEN** the pane SHALL switch to `diff` mode automatically

#### Scenario: Regenerate keeps current mode if content didn't change

- **GIVEN** the pane is on `edit` mode and the regenerate mutation is
  in flight
- **WHEN** the mutation resolves with `current.free_form_markdown` equal
  to `previous_free_form_markdown` (rare: identical regeneration)
- **THEN** the pane SHALL stay on `edit` mode (no auto-switch)
