## ADDED Requirements

### Requirement: /meetings and /meetings/calendar SHALL share a Kanban / 行事曆 tab bar

Both `/meetings` and `/meetings/calendar` SHALL mount a shared
`<MeetingsViewTabs value="kanban" | "calendar" />` component
above their main content. The tab labels SHALL be **Kanban**
(value="kanban") and **行事曆** (value="calendar") in zh-TW, and
**Kanban** / **Calendar** in en.

The component SHALL be controlled — `value` is set from the parent
route, and `onValueChange` calls `useNavigate()` to navigate to the
inactive tab's route. The URL SHALL be the single source of truth
for which tab is active.

#### Scenario: Switching from Kanban to 行事曆

- **GIVEN** the user is on /meetings with the Kanban tab active
- **WHEN** the user clicks the 行事曆 tab
- **THEN** the browser SHALL navigate to /meetings/calendar
- **AND** the calendar page SHALL render with the 行事曆 tab marked
  active

#### Scenario: Switching from 行事曆 back to Kanban

- **GIVEN** the user is on /meetings/calendar with the 行事曆 tab
  active
- **WHEN** the user clicks the Kanban tab
- **THEN** the browser SHALL navigate to /meetings
- **AND** the list page SHALL render with the Kanban tab marked
  active

### Requirement: NewMeeting SHALL honour ?from=calendar for redirect on submit and cancel

The `/meetings/new` route SHALL accept an optional `from` search
parameter. The only allowed value SHALL be `"calendar"`; any
other value (or absence) SHALL be treated as if the parameter
were missing.

When `from === "calendar"`:
- Successful create (mutation resolves with the new meeting) SHALL
  navigate to `/meetings/calendar` with `replace: true`.
- Clicking Cancel SHALL navigate to `/meetings/calendar`.

When `from` is absent (or any other value):
- Successful create SHALL navigate to `/meetings/$id` with the
  newly created meeting's id (existing behaviour).
- Clicking Cancel SHALL navigate to `/meetings` (existing behaviour).

The /meetings/calendar route's "新會議" Link SHALL pass
`search={{ from: "calendar" }}` so the round trip works
end-to-end. The /meetings (Kanban) page's "新會議" Link SHALL NOT
pass the parameter.

#### Scenario: Calendar → New → submit returns to calendar

- **GIVEN** the user is on /meetings/calendar and clicks "新會議"
- **AND** is taken to /meetings/new?from=calendar
- **WHEN** the user fills the form and submits
- **THEN** the browser SHALL navigate to /meetings/calendar (NOT
  /meetings/$id) once the mutation resolves

#### Scenario: Calendar → New → cancel returns to calendar

- **GIVEN** the same setup as above
- **WHEN** the user clicks Cancel instead of submitting
- **THEN** the browser SHALL navigate to /meetings/calendar (NOT
  /meetings)

#### Scenario: Kanban → New → submit goes to detail page

- **GIVEN** the user is on /meetings (Kanban) and clicks "新會議"
- **AND** is taken to /meetings/new (no `from` parameter)
- **WHEN** the user fills the form and submits
- **THEN** the browser SHALL navigate to /meetings/$id with the
  newly created meeting's id, replicating the pre-change behaviour

#### Scenario: Unknown ?from value falls back to default

- **GIVEN** the user lands on /meetings/new?from=somewhere-else
- **WHEN** the user submits the form
- **THEN** the browser SHALL navigate to /meetings/$id (the default
  path), NOT to /meetings/calendar
