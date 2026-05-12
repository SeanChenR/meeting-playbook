## ADDED Requirements

### Requirement: /meetings SHALL render meetings as a 3-column date-bucketed Kanban

The `/meetings` route SHALL replace the previous auto-fill grid
(`grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`)
with a 3-column Kanban board grouped by date.

The three columns SHALL be:

- **即將到來** (upcoming) — meetings whose `status` is
  `"in_progress"` regardless of date, OR meetings whose `status` is
  `"scheduled"` and whose `scheduled_start_at` falls in
  `[startOfToday, startOfToday + 7 days)`. Column accent: primary.
- **未來** (future) — meetings whose `status` is `"scheduled"` and
  whose `scheduled_start_at` is at or beyond `startOfToday + 7
  days`, OR meetings with `status === "scheduled"` and no
  `scheduled_start_at` set. Column accent: muted-foreground.
- **已結束** (past) — meetings whose `status` is `"completed"`, OR
  meetings whose `status` is `"scheduled"` but whose
  `scheduled_start_at` is before `startOfToday` (overdue, never
  started). Column accent: secondary (the new teal token from
  `ui-design-system`).

Bucket assignment SHALL be implemented by a pure helper function
`getMeetingDateBucket(meeting, now)` exported from
`packages/web/src/lib/meetings-bucket.ts`. The helper SHALL be
called from the Kanban component during render with `now = new
Date()`.

`startOfToday` SHALL be computed in the user's local timezone:
`new Date(now.getFullYear(), now.getMonth(), now.getDate())`.

Each column SHALL render:

- A header with the bucket label and a count badge
  (e.g. "即將到來 · 3").
- A vertically-scrollable card list using the existing
  `MeetingGridCard` component shape (status bar, title,
  counterparty, time, duration).
- An empty-state hint ("此區段暫無會議" zh-TW / "No meetings in
  this bucket" en) when the bucket is empty.

The Kanban container SHALL use
`grid-template-columns: repeat(3, minmax(280px, 1fr))` so the
columns expand evenly across the page width while never collapsing
below card width. Each column body SHALL `overflow-y: auto` with a
max height of `calc(100dvh - 280px)`.

Drag-and-drop reordering / cross-column drops SHALL NOT be
supported in this iteration. Cards remain pure links to
/meetings/$id.

#### Scenario: Three-bucket distribution

- **GIVEN** the backend returns five meetings with the following shapes
  (using `now = 2026-05-12T10:00:00 local`):

  | id | status        | scheduled_start_at        |
  |----|---------------|---------------------------|
  | a  | in_progress   | 2026-04-01T09:00:00       |
  | b  | scheduled     | 2026-05-13T15:00:00       |
  | c  | scheduled     | 2026-05-25T15:00:00       |
  | d  | scheduled     | null                      |
  | e  | completed     | 2026-04-15T10:00:00       |

- **WHEN** the /meetings page renders
- **THEN** column 即將到來 SHALL contain meetings `a` and `b`
- **AND** column 未來 SHALL contain meetings `c` and `d`
- **AND** column 已結束 SHALL contain meeting `e`

#### Scenario: Overdue scheduled meeting falls into 已結束

- **GIVEN** a meeting with `status === "scheduled"` and
  `scheduled_start_at = 2026-05-01T15:00:00` and the current date
  is 2026-05-12
- **WHEN** the bucket is computed
- **THEN** the meeting SHALL land in 已結束, not 即將到來

#### Scenario: Empty bucket renders the localized empty hint

- **GIVEN** the user has no meetings in the 已結束 bucket
- **WHEN** the /meetings Kanban renders
- **THEN** the 已結束 column SHALL show its label and count badge "0"
- **AND** the column body SHALL render a centred hint reading
  "此區段暫無會議" (zh-TW)

#### Scenario: Helper handles invalid scheduled_start_at safely

- **GIVEN** a meeting where `scheduled_start_at` is a string that
  fails `Date.parse` (e.g. `"not-a-date"`)
- **WHEN** `getMeetingDateBucket` is called on that meeting
- **THEN** the helper SHALL return `"past"` as a safe default
- **AND** SHALL emit a `console.warn` in dev (when `import.meta.env.DEV`)
