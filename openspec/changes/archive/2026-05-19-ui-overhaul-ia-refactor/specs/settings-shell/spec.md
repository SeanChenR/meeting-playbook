## ADDED Requirements

### Requirement: /settings/integrations SHALL be the sole canonical entry point for calendar integration

Calendar integration (the Google Calendar OAuth connection panel powered by `CalendarIntegrationPanel`) SHALL be reachable solely via `/settings/integrations`. The legacy standalone route `/calendar/import` (formerly `/calendar/upcoming`) SHALL NOT exist after this change. Any incoming user navigation to `/calendar/import` SHALL result in the application's standard 404 behavior because the route SHALL NOT be registered.

#### Scenario: standalone calendar route is unregistered

- **WHEN** the application's route tree is constructed
- **THEN** no route is registered at path `/calendar/import`
- **AND** no route is registered at path `/calendar/upcoming`

#### Scenario: settings integrations still renders the panel

- **WHEN** an authenticated user navigates to `/settings/integrations`
- **THEN** the page renders `CalendarIntegrationPanel` with the connect / disconnect controls
- **AND** the panel behavior is unchanged from prior to this change

#### Scenario: stale bookmark to legacy route 404s

- **GIVEN** a user has a bookmark to `/calendar/import` from a previous version
- **WHEN** the user opens the bookmark
- **THEN** the application renders its standard 404 / not-found surface
- **AND** there is no redirect to `/settings/integrations`
