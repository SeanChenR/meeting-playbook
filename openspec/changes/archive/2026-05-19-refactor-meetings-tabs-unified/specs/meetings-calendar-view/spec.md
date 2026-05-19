## MODIFIED Requirements

### Requirement: GET /meetings/calendar renders the user's meetings on a month or week grid

The web client SHALL register a single route at `/meetings` that accepts an optional `view` search parameter with allowed values `kanban` (default when absent or unrecognized) and `calendar`. When `view === "calendar"`, the route SHALL render the meetings calendar visualisation using `react-big-calendar` with the `date-fns` localizer. The grid SHALL support exactly two views: `month` (default) and `week`. A toolbar above the grid SHALL allow the user to switch between these two views and navigate forward/backward by one period. The calendar week SHALL start on Monday. Only meetings with non-null `scheduled_start_at` SHALL appear on the grid; meetings whose `scheduled_start_at` is null SHALL be listed separately (see the unscheduled-list requirement). Each rendered event SHALL show the meeting's title.

The legacy path `/meetings/calendar` SHALL NOT be a registered route after this change; loading it SHALL produce the router's not-found behaviour.

#### Scenario: Month view shows meetings in their scheduled day cell

- **GIVEN** an authenticated user has three meetings: A scheduled `2026-06-01T10:00:00Z`, B scheduled `2026-06-15T14:00:00Z`, C with `scheduled_start_at = null`
- **WHEN** the user opens `/meetings?view=calendar`
- **THEN** the month grid SHALL render meeting A in the cell for `2026-06-01`, meeting B in the cell for `2026-06-15`, and SHALL NOT render meeting C in any grid cell

#### Scenario: Week view defaults to current week

- **GIVEN** the current date is `2026-05-12` (a Tuesday)
- **WHEN** the user clicks the Week toggle in the calendar toolbar
- **THEN** the calendar SHALL render the week view starting on `2026-05-11` (Monday) and ending on `2026-05-17` (Sunday)

#### Scenario: Legacy /meetings/calendar path is no longer registered

- **WHEN** the user navigates to `/meetings/calendar`
- **THEN** the router SHALL NOT render the calendar view
- **AND** the not-found surface SHALL appear (the route does not exist)

### Requirement: Meeting list and calendar view are reachable via reciprocal toggle buttons

The `/meetings` route SHALL render a shared `MeetingsViewTabs` component whose two triggers toggle the page's `view` search parameter between `kanban` and `calendar`. Activating the calendar trigger SHALL update the URL to `/meetings?view=calendar` (preserving all other search parameters). Activating the Kanban trigger SHALL remove `view` from the URL (yielding `/meetings`, preserving all other search parameters). Toggling SHALL NOT trigger a full route remount; the user's authenticated session and meeting data SHALL be preserved across the toggle.

#### Scenario: Toggle from Kanban to calendar and back

- **GIVEN** the user is on `/meetings` (Kanban panel visible)
- **WHEN** the user clicks the Calendar trigger
- **THEN** the URL SHALL update to `/meetings?view=calendar` and the calendar panel SHALL render
- **WHEN** the user then clicks the Kanban trigger
- **THEN** the URL SHALL update to `/meetings` and the Kanban panel SHALL render

#### Scenario: Toggling preserves other search parameters

- **GIVEN** the user is on `/meetings?tag_ids=abc,def` (Kanban panel visible, tag filter active)
- **WHEN** the user clicks the Calendar trigger
- **THEN** the URL SHALL be `/meetings?tag_ids=abc,def&view=calendar` (parameter order is implementation-defined; the `tag_ids` value MUST be preserved verbatim)

### Requirement: /meetings and /meetings/calendar SHALL share a Kanban / 行事曆 tab bar

The single `/meetings` route SHALL mount one instance of `<MeetingsViewTabs value="kanban" | "calendar" />` in a row above the panel content. The component SHALL persist across `view` toggles (not unmount/remount), so the active-tab pill SHALL slide between triggers without interruption. The tab labels SHALL be **Kanban** (value="kanban") and **行事曆** (value="calendar") in zh-TW, and **Kanban** / **Calendar** in en.

The component SHALL be controlled — `value` SHALL be derived from the current `view` search parameter (defaulting to `"kanban"` when absent or unrecognised), and `onValueChange` SHALL update the `view` search parameter via `useNavigate()`. The URL SHALL be the single source of truth for which tab is active.

#### Scenario: Switching from Kanban to 行事曆

- **GIVEN** the user is on `/meetings` with the Kanban tab active
- **WHEN** the user clicks the 行事曆 tab
- **THEN** the URL SHALL update to `/meetings?view=calendar`
- **AND** the calendar panel SHALL animate into view with the 行事曆 tab marked active
- **AND** the `MeetingsViewTabs` element SHALL remain the same DOM instance throughout (no unmount)

#### Scenario: Switching from 行事曆 back to Kanban

- **GIVEN** the user is on `/meetings?view=calendar` with the 行事曆 tab active
- **WHEN** the user clicks the Kanban tab
- **THEN** the URL SHALL update to `/meetings`
- **AND** the Kanban panel SHALL animate into view with the Kanban tab marked active

### Requirement: NewMeeting SHALL honour ?from=calendar for redirect on submit and cancel

The `/meetings/new` route SHALL accept an optional `from` search parameter. The only allowed value SHALL be `"calendar"`; any other value (or absence) SHALL be treated as if the parameter were missing.

When `from === "calendar"`:
- Successful create (mutation resolves with the new meeting) SHALL navigate to `/meetings?view=calendar` with `replace: true`.
- Clicking Cancel SHALL navigate to `/meetings?view=calendar`.

When `from` is absent (or any other value):
- Successful create SHALL navigate to `/meetings/$id` with the newly created meeting's id (existing behaviour).
- Clicking Cancel SHALL navigate to `/meetings` (existing behaviour).

The Calendar panel's "新會議" Link (rendered when `view=calendar`) SHALL pass `search={{ from: "calendar" }}` so the round trip works end-to-end. The Kanban panel's "新會議" Link SHALL NOT pass the parameter.

#### Scenario: Calendar → New → submit returns to calendar view

- **GIVEN** the user is on `/meetings?view=calendar` and clicks "新會議"
- **AND** is taken to `/meetings/new?from=calendar`
- **WHEN** the user fills the form and submits
- **THEN** the browser SHALL navigate to `/meetings?view=calendar` (NOT `/meetings/$id`) once the mutation resolves

#### Scenario: Calendar → New → cancel returns to calendar view

- **GIVEN** the same setup as above
- **WHEN** the user clicks Cancel instead of submitting
- **THEN** the browser SHALL navigate to `/meetings?view=calendar` (NOT `/meetings`)

#### Scenario: Kanban → New → submit goes to detail page

- **GIVEN** the user is on `/meetings` (Kanban) and clicks "新會議"
- **AND** is taken to `/meetings/new` (no `from` parameter)
- **WHEN** the user fills the form and submits
- **THEN** the browser SHALL navigate to `/meetings/$id` with the newly created meeting's id, replicating the pre-change behaviour

#### Scenario: Unknown ?from value falls back to default

- **GIVEN** the user lands on `/meetings/new?from=somewhere-else`
- **WHEN** the user submits the form
- **THEN** the browser SHALL navigate to `/meetings/$id` (the default path), NOT to `/meetings?view=calendar`

## ADDED Requirements

### Requirement: View switch SHALL animate the panel without remounting the tab bar

The `/meetings` route SHALL render the Kanban and calendar panels inside an `AnimatePresence` boundary. Switching `view` SHALL trigger a direction-aware horizontal slide:

- `kanban → calendar`: outgoing Kanban panel SHALL slide left; incoming calendar panel SHALL slide in from the right.
- `calendar → kanban`: outgoing calendar panel SHALL slide right; incoming Kanban panel SHALL slide in from the left.

The animation SHALL use `mode="wait"` so the outgoing panel completes its exit before the incoming panel begins entering. When the browser's `prefers-reduced-motion` is enabled (as reported by `useReducedMotion`), the transition duration SHALL be 0.

The `MeetingsViewTabs` element SHALL be mounted in the wrapper, **outside** the `AnimatePresence` boundary; it MUST NOT unmount during view switches.

#### Scenario: Forward switch slides panel from the right

- **GIVEN** the user is on `/meetings` (Kanban panel visible)
- **WHEN** the user clicks the calendar trigger
- **THEN** the Kanban panel SHALL exit horizontally to the left
- **AND** the calendar panel SHALL enter horizontally from the right
- **AND** the two panels SHALL NOT both be visible at the same animation frame (mode="wait")

#### Scenario: Reverse switch slides panel from the left

- **GIVEN** the user is on `/meetings?view=calendar` (calendar panel visible)
- **WHEN** the user clicks the Kanban trigger
- **THEN** the calendar panel SHALL exit horizontally to the right
- **AND** the Kanban panel SHALL enter horizontally from the left

#### Scenario: Reduced-motion users skip the slide

- **GIVEN** the user has `prefers-reduced-motion: reduce` set
- **WHEN** the user toggles between Kanban and calendar
- **THEN** the panel SHALL swap with zero-duration transition (no perceptible slide)
- **AND** the URL and active-tab state SHALL still update correctly
