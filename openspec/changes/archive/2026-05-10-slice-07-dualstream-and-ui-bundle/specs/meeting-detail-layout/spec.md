## ADDED Requirements

### Requirement: Detail page exposes a layout switcher persisted across sessions

The meeting detail page SHALL render a layout switcher control with two modes: `stack` (vertical) and `columns` (three-column). The selected mode SHALL persist in `localStorage` under the key `meeting-detail.layout`. On initial load when the key is unset or holds an invalid value, the layout SHALL default to `columns`. The switcher SHALL be rendered in the page top bar to the right of the back-link, MUST be reachable by keyboard, and MUST update the rendered layout immediately when toggled (no page reload).

#### Scenario: Switching layout persists and survives reload

- **GIVEN** a user opens `/meetings/{id}` with no prior layout preference
- **WHEN** the user clicks the Stack icon button in the top bar
- **THEN** the page SHALL re-render in stack mode immediately, and `localStorage["meeting-detail.layout"]` SHALL equal `"stack"`; reloading the page SHALL render the page in stack mode

#### Scenario: Invalid stored value falls back to columns

- **GIVEN** `localStorage["meeting-detail.layout"]` holds the string `"weird-value"`
- **WHEN** the user opens `/meetings/{id}`
- **THEN** the page SHALL render in columns mode (the default), without throwing

### Requirement: Columns mode renders three panes in a 30/40/30 grid with full-width meta

In columns mode the meeting detail page SHALL render three vertical panes side-by-side: Playbook (30% width), Transcript (40% width), and Advisor (30% width). The meeting meta card (title, status pill, Start/End buttons, capture indicator) SHALL render as a full-width horizontal bar above the columns and SHALL NOT be placed inside any column. The grid widths SHALL be fixed (no drag-resize). Each column SHALL scroll independently of the others.

#### Scenario: Columns mode applies the fixed 30/40/30 grid

- **GIVEN** the page is in columns mode and the viewport is wider than 1024px
- **WHEN** the page renders
- **THEN** the three column wrappers SHALL have CSS computed widths in the proportions 30%, 40%, and 30%, and the meta card SHALL span the full content width above them

### Requirement: Stack mode renders the three panes vertically in P-T-A order

In stack mode the meeting detail page SHALL render the same three panes one above another in the order Playbook → Transcript → Advisor (top to bottom). The meeting meta card SHALL render above all three. Each pane SHALL be full content width.

#### Scenario: Stack mode renders the panes in order

- **GIVEN** the page is in stack mode
- **WHEN** the page renders
- **THEN** in document source order the Playbook pane SHALL appear before the Transcript pane, which SHALL appear before the Advisor pane, all full-width

### Requirement: Advisor pane shows a placeholder until the tactical advisor capability ships

The Advisor pane SHALL be rendered in both layout modes carrying placeholder copy localized via `meetings.detail.advisorPlaceholder` (e.g., "Tactical advisor 將在 Slice 8 上線" / "Tactical advisor lands in Slice 8"). It MUST NOT render any input control or button until that future slice activates the capability.

#### Scenario: Placeholder text is shown in both modes

- **GIVEN** the meeting page is in either stack or columns mode
- **WHEN** the page renders
- **THEN** the Advisor pane SHALL contain the localized placeholder string and SHALL NOT contain any `<input>`, `<button>`, or `<textarea>` element

### Requirement: ProtectedShell exposes a fullBleed prop that disables the centered max-width container

The `ProtectedShell` component SHALL accept an optional `fullBleed?: boolean` prop defaulting to `false`. When `fullBleed` is `false`, the shell SHALL preserve its existing centered max-width content container. When `fullBleed` is `true`, the shell SHALL render its content area without a max-width constraint, allowing the page to occupy the full browser viewport width. The detail page SHALL always pass `fullBleed`. List, new, login, signup, home, and calendar-import routes SHALL NOT pass it.

#### Scenario: Detail page renders edge-to-edge

- **WHEN** the user opens `/meetings/{id}`
- **THEN** the rendered content area SHALL have no max-width style applied at the shell level, allowing nested layouts (columns or stack) to use the full viewport width

#### Scenario: Other routes keep the centered container

- **WHEN** the user opens `/meetings`
- **THEN** the rendered content area SHALL be wrapped in the existing centered max-width container

### Requirement: Columns mode three panes share equal visible height (slice-7 round 2)

In columns mode on viewports >=1024px, the three content panes (Playbook, Transcript, Advisor) SHALL render at IDENTICAL visible height, so the row of columns presents as a balanced grid rather than a jagged silhouette. The shared height SHALL be derived from the available viewport height minus the header + meta-card stack (target: `calc(100vh - 220px)` give-or-take a few pixels). Content overflow within any pane SHALL be confined to that pane's own scroll container so a long transcript does not push other panes downward.

The equal-height constraint SHALL apply ONLY in columns mode. Stack mode preserves natural per-pane heights (vertical layout doesn't suffer the imbalance issue).

#### Scenario: Columns mode panes are visually balanced

- **GIVEN** detail page in columns mode on a 1440-wide viewport with a tall transcript and a short playbook
- **WHEN** the page renders
- **THEN** the three pane wrappers (`data-testid="detail-pane-playbook"`, `detail-pane-transcript`, `detail-pane-advisor`) SHALL have equal computed heights (within 1px tolerance), and each pane's internal scroll SHALL be independent

#### Scenario: Stack mode preserves natural heights

- **GIVEN** detail page in stack mode with mixed-length pane content
- **WHEN** the page renders
- **THEN** each pane SHALL size to its own content (no fixed height applied); the equal-height constraint MUST NOT activate
