## ADDED Requirements

### Requirement: The "Import from calendar" affordance on /meetings SHALL navigate to /settings/integrations

The "從行事曆匯入" / "Import from calendar" button rendered on the Meetings list page (kanban / calendar / list views) SHALL link to `/settings/integrations` as the single canonical entry point for Google Calendar connection. The button SHALL NOT link to any standalone `/calendar/*` route.

#### Scenario: button on meetings list navigates to settings integrations

- **WHEN** an authenticated user clicks the "Import from calendar" button on `/meetings`
- **THEN** the router navigates to `/settings/integrations`
- **AND** the user lands on the integrations settings page rendering `CalendarIntegrationPanel`

#### Scenario: no link to standalone calendar route

- **WHEN** the meetings list is rendered
- **THEN** no element has `href` or TanStack `to` pointing to `/calendar/import` or `/calendar/upcoming`
