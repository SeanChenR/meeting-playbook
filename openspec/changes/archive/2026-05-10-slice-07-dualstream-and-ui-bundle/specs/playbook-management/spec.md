## MODIFIED Requirements

### Requirement: PlaybookPane UI exposes a free-form view, a structured view, and a save action

The web UI SHALL provide a `PlaybookPane` component that the meeting detail page mounts. The component SHALL render a top-level view-mode toggle with two states: a free-form view that exposes a single editor for `free_form_markdown`, and a structured view that exposes six labeled editors, one per structured field (`objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`).

The free-form view's primary editor SHALL be a plain `<textarea>` containing the markdown source. Inside the free-form view, a SECOND smaller toggle SHALL switch between two sub-modes:
- **Edit** (default): the `<textarea>` is shown for editing markdown source.
- **Preview**: a read-only rendered view powered by `react-markdown` + `remark-gfm` + `rehype-sanitize`. Switching to Preview MUST NOT mutate the `<textarea>` value; switching back to Edit MUST restore the user's caret position to the beginning of the textarea (or an acceptable default — caret restoration is not strictly required).

The DB storage format for `free_form_markdown` SHALL remain markdown text (no schema change); the textarea writes the value verbatim, and Preview never mutates it. Switching between free-form and structured views MUST NOT discard any unsaved edits in either view. A save action MUST send a single PUT request carrying the current values of all seven fields and MUST refresh the displayed content after the response succeeds.

The free-form view MUST NOT render a TipTap WYSIWYG editor or any toolbar of formatting buttons. Markdown is typed directly in the textarea using standard markdown syntax (`**bold**`, `# Heading`, `- bullet`, etc.).

#### Scenario: Toggle preserves unsaved edits in both views

- **GIVEN** the user has typed text into the free-form `<textarea>` and into the structured `objective` field, neither saved
- **WHEN** the user toggles to the structured view, then back to free-form
- **THEN** both the free-form text (in the textarea) and the structured `objective` text SHALL still be present

#### Scenario: Save dispatches a PUT and refreshes the displayed content

- **GIVEN** the user has typed values into all seven fields (free-form value typed directly as markdown into the textarea)
- **WHEN** the user clicks the save button
- **THEN** the component SHALL issue exactly one `PUT /api/meetings/{id}/playbook` request whose body contains all seven fields with the typed values; the `free_form_markdown` field's value SHALL equal the textarea's current `value` property byte-for-byte; the component SHALL display those values after the response resolves

#### Scenario: Preview sub-toggle renders rendered markdown without mutating the source

- **GIVEN** the meeting's `free_form_markdown` field is stored in the database as `"# Goals\n\n- Discuss Q3 numbers\n- **Confirm deadlines**"`
- **WHEN** the playbook detail loads, the user opens the free-form view, and clicks the Preview sub-toggle
- **THEN** the rendered output SHALL contain an H1 reading "Goals", followed by an unordered list with two items, the second of which contains a bold "Confirm deadlines" run; the underlying `<textarea>`'s `value` MUST remain the original markdown source unchanged

#### Scenario: Free-form view exposes Edit/Preview sub-toggle (no formatting toolbar)

- **GIVEN** the free-form view is visible
- **WHEN** the page renders
- **THEN** the view SHALL contain a sub-toggle with exactly two options labeled via `playbook.freeform.editTab` and `playbook.freeform.previewTab` i18n keys; the view MUST NOT render any TipTap editor instance, formatting toolbar, or `playbook.toolbar.*` i18n keys
