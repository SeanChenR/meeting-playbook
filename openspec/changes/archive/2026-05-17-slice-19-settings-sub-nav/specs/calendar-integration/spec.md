## MODIFIED Requirements

### Requirement: Calendar import lives at /calendar/import to disambiguate from the meetings calendar view

The web client SHALL render the Google Calendar connection-status UI (connect button when disconnected, upcoming-events list when connected, one-click-import wizard) at the URL path `/settings/integrations`, nested inside the settings shell. The previously registered route `/calendar/import` MUST remain reachable as a redirect-only route: visiting `/calendar/import` SHALL redirect to `/settings/integrations` via `beforeLoad` so no intermediate page renders. The page's calendar-related business logic and i18n keys (`calendar.heading`, `calendar.empty`, etc.) MUST NOT change; only the canonical URL moves and the legacy URL becomes a redirect. All internal links in the web client that previously pointed to `/calendar/import` SHALL be updated to point to `/settings/integrations`.

#### Scenario: /settings/integrations renders the connection panel

- **WHEN** an authenticated user navigates to `/settings/integrations`
- **THEN** the page SHALL render the upcoming-events list (or the connect-Calendar prompt if not connected), behaving as the previous `/calendar/import` URL did, AND the page SHALL be wrapped in the settings sub-nav shell

#### Scenario: /calendar/import redirects to /settings/integrations

- **WHEN** an authenticated user navigates to `/calendar/import`
- **THEN** the browser SHALL be redirected to `/settings/integrations` AND the redirect MUST happen in `beforeLoad` so the legacy URL never renders a calendar UI of its own

#### Scenario: Internal navigation uses the new path

- **GIVEN** any internal link in the web client (home, navbar, meetings list, user menu) that previously had `to="/calendar/import"`
- **WHEN** the link is rendered after this change
- **THEN** the link's `to` attribute SHALL equal `"/settings/integrations"` (not `"/calendar/import"`)
