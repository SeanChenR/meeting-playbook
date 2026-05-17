## ADDED Requirements

### Requirement: `PlaybookRead` schema exposes the previous-version snapshot

The `PlaybookRead` Pydantic schema returned by every playbook-bearing
endpoint (`GET /api/meetings/{meeting_id}/playbook`, regenerate response,
discard/restore response, and any future read) SHALL include three new
fields introduced by slice-23:

- `previous_free_form_markdown: str | None`
- `previous_updated_at: datetime | None`
- `has_previous_version: bool` (derived: `previous_free_form_markdown is not None`)

The full row shape SHALL be returned on every call so the frontend never
has to fetch a second time to learn the snapshot state.

#### Scenario: GET on row without snapshot returns null previous fields

- **GIVEN** a freshly-created playbook row (no regenerate has happened)
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes `"previous_free_form_markdown": null`,
  `"previous_updated_at": null`, and `"has_previous_version": false`

#### Scenario: GET on row with snapshot returns full previous fields

- **GIVEN** a row whose `previous_free_form_markdown = "draft v1"` and
  `previous_updated_at = "2026-05-17T10:00:00+00:00"`
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes
  `"previous_free_form_markdown": "draft v1"`,
  `"previous_updated_at": "2026-05-17T10:00:00+00:00"`, and
  `"has_previous_version": true`

### Requirement: User-save upsert preserves the previous-version snapshot

`PlaybookRepository.upsert_for_meeting(meeting_id, payload)` — the
user-save path invoked by `PUT /api/meetings/{meeting_id}/playbook` —
SHALL NOT modify the three `previous_*` columns introduced by slice-23.
Only the regenerate path (`snapshot_then_upsert`) and the explicit
`discard_previous` / `restore_previous` endpoints SHALL touch them.

This separation guarantees the snapshot always refers to the version
that existed immediately before the last AI regeneration — never an
arbitrary middle save.

#### Scenario: Save after regenerate keeps snapshot intact

- **GIVEN** a row where `free_form_markdown = "v2"` and
  `previous_free_form_markdown = "v1"`
- **WHEN** the user edits the freeform text and PUTs an upsert with
  `free_form_markdown = "v2-edited"`
- **THEN** the row's `free_form_markdown` is `"v2-edited"`
- **AND** the row's `previous_free_form_markdown` is still `"v1"`
- **AND** the row's `previous_updated_at` is unchanged

## MODIFIED Requirements

### Requirement: PlaybookPane UI exposes a free-form view, a structured view, and a save action

The web UI SHALL provide a `PlaybookPane` component that the meeting detail page mounts. The component SHALL render a top-level view-mode toggle with two states: a free-form view that exposes a single editor for `free_form_markdown`, and a structured view that exposes six labeled editors, one per structured field (`objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`).

The free-form view's primary editor SHALL be a plain `<textarea>` containing the markdown source. Inside the free-form view, a sub-mode toggle SHALL switch between **two or three** sub-modes:

- **Edit** (default): the `<textarea>` is shown for editing markdown source.
- **Preview**: a read-only rendered view powered by `react-markdown` + `remark-gfm` + `rehype-sanitize`. Switching to Preview MUST NOT mutate the `<textarea>` value; switching back to Edit MUST restore the user's caret position to the beginning of the textarea (or an acceptable default — caret restoration is not strictly required).
- **Diff** (slice-23, conditional): a third sub-mode that SHALL render the line-level visual difference between `previous_free_form_markdown` and the current `free_form_markdown`, plus action buttons that map to the discard-previous / restore-previous / cherry-pick endpoints. The Diff toggle button SHALL appear in the sub-mode group only when `query.data?.has_previous_version === true`. When `has_previous_version === false`, the sub-mode toggle SHALL render exactly two buttons (Edit and Preview), matching the slice-7 / slice-20a contract.

Switching out of Diff mode SHALL NOT mutate the textarea value or the snapshot columns; only the explicit action buttons inside Diff mode mutate state.

#### Scenario: Two sub-mode buttons when no snapshot exists

- **GIVEN** a playbook detail page mounted for a row where `has_previous_version === false`
- **WHEN** the pane renders
- **THEN** the sub-mode toggle SHALL contain exactly two buttons: Edit and Preview

#### Scenario: Three sub-mode buttons when snapshot exists

- **GIVEN** a playbook detail page mounted for a row where `has_previous_version === true`
- **WHEN** the pane renders
- **THEN** the sub-mode toggle SHALL contain three buttons: Edit, Preview, and Diff

#### Scenario: Switching between sub-modes does not mutate state

- **GIVEN** the pane is in Diff mode with cherry-pick decisions made by the user
- **WHEN** the user clicks the Edit sub-mode toggle
- **THEN** the textarea value SHALL be the row's current `free_form_markdown` (unchanged from before entering Diff mode)
- **AND** the row's `previous_*` columns SHALL be unchanged
