## ADDED Requirements

### Requirement: GET /meetings/calendar renders the user's meetings on a month or week grid

The web client SHALL register a route at `/meetings/calendar` that fetches the authenticated user's meetings and renders them on a calendar grid using `react-big-calendar` with the `date-fns` localizer. The grid SHALL support exactly two views: `month` (default) and `week`. A toolbar above the grid SHALL allow the user to switch between these two views and navigate forward/backward by one period. The calendar week SHALL start on Monday. Only meetings with non-null `scheduled_start_at` SHALL appear on the grid; meetings whose `scheduled_start_at` is null SHALL be listed separately (see the unscheduled-list requirement). Each rendered event SHALL show the meeting's title.

#### Scenario: Month view shows meetings in their scheduled day cell

- **GIVEN** an authenticated user has three meetings: A scheduled `2026-06-01T10:00:00Z`, B scheduled `2026-06-15T14:00:00Z`, C with `scheduled_start_at = null`
- **WHEN** the user opens `/meetings/calendar`
- **THEN** the month grid SHALL render meeting A in the cell for `2026-06-01`, meeting B in the cell for `2026-06-15`, and SHALL NOT render meeting C in any grid cell

#### Scenario: Week view defaults to current week

- **GIVEN** the current date is `2026-05-12` (a Tuesday)
- **WHEN** the user clicks the Week toggle in the calendar toolbar
- **THEN** the calendar SHALL render the week view starting on `2026-05-11` (Monday) and ending on `2026-05-17` (Sunday)

### Requirement: Calendar event color reflects meeting status

Each rendered calendar event SHALL apply a status-derived color class. Meetings with `status = "scheduled"` SHALL render with a blue accent, `status = "in_progress"` SHALL render with a green accent, and `status = "completed"` SHALL render with a grey accent. The exact color tokens SHALL come from the application's existing Tailwind theme so dark and light modes both remain legible.

#### Scenario: Three meetings render in three distinct status colors

- **GIVEN** three meetings of statuses `scheduled`, `in_progress`, and `completed` all scheduled in the current month
- **WHEN** the calendar renders the month view
- **THEN** the three event blocks SHALL each carry a CSS class corresponding to a distinct status accent (blue, green, grey respectively)

### Requirement: Clicking a calendar event navigates to that meeting's detail page

Clicking an event card on the calendar grid (or pressing Enter while it is keyboard-focused) SHALL navigate the user to `/meetings/{id}` for that meeting using the existing TanStack Router navigation. No additional confirmation dialog SHALL be shown.

#### Scenario: Click navigates to detail

- **GIVEN** meeting `m_abc` is rendered on the calendar grid
- **WHEN** the user clicks its event card
- **THEN** the router SHALL navigate to `/meetings/m_abc`

### Requirement: Clicking an empty day cell navigates to the new-meeting form with the date pre-filled

Clicking an empty day cell on the month or week grid SHALL navigate the user to `/meetings/new?date=YYYY-MM-DD` where the date matches the clicked cell. The new-meeting form SHALL read the `date` query parameter and pre-fill its optional schedule date field with that value, using `09:00` as the default time when no time is provided.

#### Scenario: Click empty day pre-fills new form

- **GIVEN** the user is viewing the month grid
- **WHEN** the user clicks the empty cell for `2026-06-20`
- **THEN** the router SHALL navigate to `/meetings/new?date=2026-06-20` and the new-meeting form SHALL render with its scheduled-date input set to `2026-06-20` and time defaulting to `09:00`

### Requirement: Meetings without a scheduled start time appear in a collapsible unscheduled list

Below the calendar grid the page SHALL render a collapsible panel labeled via `meetings.calendar.unscheduledTitle`. The panel SHALL list every meeting belonging to the authenticated user whose `scheduled_start_at` is null, showing the meeting title and counterparty display name. Clicking a row SHALL navigate to that meeting's detail page. When zero meetings are unscheduled the panel MUST NOT be rendered. The panel SHALL be collapsed by default.

#### Scenario: Unscheduled meetings appear in the panel

- **GIVEN** the authenticated user has two meetings with null `scheduled_start_at` and ten meetings with non-null values
- **WHEN** the calendar page renders
- **THEN** the page SHALL render an "Unscheduled Meetings" collapsible (initially collapsed) which when expanded SHALL show exactly those two unscheduled meetings as clickable rows

#### Scenario: No unscheduled meetings hides the panel

- **GIVEN** all of the user's meetings have non-null `scheduled_start_at`
- **WHEN** the calendar page renders
- **THEN** the unscheduled panel SHALL NOT be present in the DOM

### Requirement: Meeting list and calendar view are reachable via reciprocal toggle buttons

The `/meetings` list page SHALL render a toggle button in its top bar labeled via `meetings.list.toggleCalendar` that navigates to `/meetings/calendar`. The `/meetings/calendar` page SHALL render the symmetric toggle (via `meetings.calendar.toggleList`) that navigates back to `/meetings`. Toggling SHALL preserve the user's authenticated session and SHALL NOT mutate any meeting data.

#### Scenario: Toggle from list to calendar and back

- **WHEN** the user is on `/meetings` and clicks the Calendar-view toggle button
- **THEN** the router SHALL navigate to `/meetings/calendar`; clicking the List-view toggle on that page SHALL navigate back to `/meetings`

### Requirement: Empty calendar shows a localized empty-state message

When the authenticated user has zero meetings whose `scheduled_start_at` falls within the currently displayed range (month or week), the calendar grid SHALL render an empty grid plus the localized empty-state message via key `meetings.calendar.empty` (e.g., "本月無會議" / "No meetings in this period").

#### Scenario: Empty month renders empty-state copy

- **GIVEN** the authenticated user has zero scheduled meetings in the current month
- **WHEN** the calendar page opens in month view
- **THEN** the grid SHALL render with no event cards and the page SHALL display the localized `meetings.calendar.empty` message
