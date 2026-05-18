## MODIFIED Requirements

### Requirement: PlaybookPane UI exposes a free-form view, a structured view, and a save action

The web UI SHALL provide a `PlaybookPane` component that the meeting detail page mounts. The component SHALL render a top-level view-mode toggle with two states: a free-form view that exposes a single editor for `free_form_markdown`, and a structured view that exposes six labeled editors, one per structured field (`objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`).

The free-form view's primary editor SHALL be a plain `<textarea>` containing the markdown source. Inside the free-form view, a sub-mode toggle SHALL switch between **two or three** sub-modes:

- **Preview** (default): a read-only rendered view powered by `react-markdown` + `remark-gfm` + `rehype-sanitize`. When the `PlaybookPane` first mounts for a given `meetingId`, the sub-mode state SHALL initialize to `"preview"` so the user sees rendered markdown (headings as large text, list markers as bullets, bold spans, GFM tables, sanitized code blocks) without having to toggle. Switching into Preview from another sub-mode MUST NOT mutate the textarea draft state. The `freeform-preview-tab` button SHALL have `aria-pressed="true"` on initial mount; `freeform-edit-tab` SHALL have `aria-pressed="false"` on initial mount.
- **Edit**: the `<textarea>` is shown for editing markdown source. The user SHALL reach Edit by clicking the `freeform-edit-tab` button. Switching back to Preview MUST NOT mutate the textarea draft state; switching from Preview into Edit MUST surface a textarea pre-populated with the current draft markdown (caret position restoration is not strictly required).
- **Diff** (slice-23, conditional): a third sub-mode that SHALL render the line-level visual difference between `previous_free_form_markdown` and the current `free_form_markdown`, plus action buttons that map to the discard-previous / restore-previous / cherry-pick endpoints. The Diff toggle button SHALL appear in the sub-mode group only when `query.data?.has_previous_version === true`. When `has_previous_version === false`, the sub-mode toggle SHALL render exactly two buttons (Edit and Preview), matching the slice-7 / slice-20a contract.

Switching out of Diff mode SHALL NOT mutate the textarea value or the snapshot columns; only the explicit action buttons inside Diff mode mutate state.

When the user is in Diff sub-mode and the server-side snapshot disappears (i.e. `query.data?.has_previous_version` transitions to `false`), the component SHALL fall back to `"preview"` sub-mode (not `"edit"`) so the post-fallback state aligns with the default mount state.

The sub-mode toggle buttons SHALL retain stable `data-testid` attributes across this change: `freeform-edit-tab`, `freeform-preview-tab`, and (conditionally) `freeform-diff-tab`. No new i18n keys are introduced; existing `playbook.freeform.editTab`, `playbook.freeform.previewTab`, and `playbook.diff.tab` keys are reused.

#### Scenario: Preview is the default sub-mode on initial mount

- **GIVEN** a `PlaybookPane` mounted for a `meetingId` whose playbook has `free_form_markdown` containing markdown source (e.g. `# Heading\n- bullet\n**bold**`)
- **WHEN** the pane finishes its first render
- **THEN** the rendered `MarkdownPreview` element (e.g. `data-testid="markdown-preview"`) SHALL be present in the DOM
- **AND** the raw `<textarea>` for `free_form_markdown` SHALL NOT be present in the DOM
- **AND** the `freeform-preview-tab` button SHALL have `aria-pressed="true"`
- **AND** the `freeform-edit-tab` button SHALL have `aria-pressed="false"`

#### Scenario: User clicks Edit to switch into the textarea

- **GIVEN** a `PlaybookPane` rendered with the default Preview sub-mode active
- **WHEN** the user clicks the `freeform-edit-tab` button
- **THEN** the raw `<textarea>` for `free_form_markdown` SHALL be present in the DOM with its `value` equal to the current draft markdown
- **AND** the `MarkdownPreview` element SHALL NOT be present in the DOM
- **AND** the `freeform-edit-tab` button SHALL have `aria-pressed="true"`
- **AND** the `freeform-preview-tab` button SHALL have `aria-pressed="false"`

#### Scenario: User switches back from Edit to Preview without losing draft

- **GIVEN** a `PlaybookPane` in Edit sub-mode with the user having typed `## new section` into the textarea (draft state updated, but not yet saved)
- **WHEN** the user clicks the `freeform-preview-tab` button
- **THEN** the `MarkdownPreview` element SHALL be present in the DOM and SHALL render the updated draft (including `## new section` as a level-2 heading)
- **AND** the `<textarea>` SHALL NOT be present in the DOM
- **AND** the in-memory draft state SHALL still contain `## new section` (verifiable by clicking `freeform-edit-tab` again and observing the textarea value)

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

#### Scenario: Snapshot disappearance from Diff falls back to Preview

- **GIVEN** the pane is in Diff sub-mode and `query.data.has_previous_version === true`
- **WHEN** the server-side snapshot is cleared (`has_previous_version` transitions to `false`, e.g. after a successful `discard_previous` mutation)
- **THEN** the component SHALL transition the sub-mode state to `"preview"` (NOT `"edit"`)
- **AND** the `MarkdownPreview` element SHALL be present in the DOM
- **AND** the Diff toggle button SHALL no longer be rendered (only Edit and Preview buttons remain)
