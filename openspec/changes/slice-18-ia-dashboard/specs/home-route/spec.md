## ADDED Requirements

### Requirement: The root route `/` SHALL render the user's home page after authentication

The web router MUST mount `<HomePage />` at `/` and MUST NOT mount any component at `/home`. Successful login MUST redirect to `/`. Visiting `/home` MUST result in the application's default not-found behavior — the router MUST NOT issue an HTTP redirect from `/home` to `/`.

#### Scenario: login redirects to root

- **WHEN** a user completes Google OAuth sign-in
- **THEN** the application navigates to `/`

#### Scenario: legacy /home is unmounted

- **WHEN** a user visits `/home` directly
- **THEN** the application renders its default not-found state (no redirect)

### Requirement: Home page SHALL render four meeting regions

`<HomePage />` MUST render four labelled regions in this order: Today's Meetings, In-Progress Recordings, Pending Items, Recently Edited. Each region MUST fetch its data via TanStack Query against the existing meeting list endpoint with the appropriate filter and ordering. Each region MUST show its own loading skeleton, empty state, and error state independently of the others.

#### Scenario: Today's Meetings region lists meetings scheduled today in ascending order

- **WHEN** the user has meetings scheduled on the current Asia/Taipei date
- **THEN** the Today's Meetings region renders those meetings sorted by `scheduled_start_at` ascending

##### Example: region data sources

| Region                  | Filter / order                                   | Limit | Empty-state copy key            |
| ----------------------- | ------------------------------------------------ | ----- | ------------------------------- |
| Today's Meetings        | `scheduled_date=<today>&order=scheduled_start_at:asc` | none  | `home.today.empty`              |
| In-Progress Recordings  | `status=in_progress`                              | none  | `home.in_progress.empty`        |
| Pending Items           | `pending=true`                                    | none  | `home.pending.empty`            |
| Recently Edited         | `order=updated_at:desc&limit=3`                   | 3     | `home.recently_edited.empty`    |

#### Scenario: a region renders empty state when its query returns no rows

- **WHEN** the user has zero meetings matching a region's filter
- **THEN** the region renders the empty-state copy keyed by its `home.*.empty` translation entry

#### Scenario: a region renders error state independently

- **WHEN** the Today's Meetings request fails with HTTP 500
- **THEN** the Today's Meetings region renders an error state and the other three regions continue to render their data

### Requirement: Home page SHALL render Quick Actions

`<HomePage />` MUST render a Quick Actions cluster containing at least two actions: "New Meeting" (navigates to the meeting creation route) and "Import from Calendar" (navigates to the calendar import route). Action labels MUST come from `home.quick_actions.*` i18n keys.

#### Scenario: New Meeting action navigates to meeting creation

- **WHEN** the user clicks the "New Meeting" Quick Action
- **THEN** the router navigates to the meeting creation route

### Requirement: Home page SHALL render a 2FA banner conditional on user state

`<HomePage />` MUST render a `<TwoFactorBanner />` if and only if the authenticated user's `twoFactorEnabled` field (read from Better Auth session) is `false`. Once the user enables 2FA and the page is re-rendered, the banner MUST disappear without manual dismissal. The banner MUST contain a call-to-action linking to `/settings/security`.

#### Scenario: 2FA banner appears when 2FA is disabled

- **WHEN** the authenticated user's `twoFactorEnabled == false`
- **THEN** `<TwoFactorBanner />` renders on the home page with a link to `/settings/security`

#### Scenario: 2FA banner disappears after enabling 2FA

- **WHEN** the user enables 2FA and returns to `/`
- **THEN** `<TwoFactorBanner />` no longer renders

### Requirement: NavBar SHALL expose three top-level destinations and route auxiliary controls into a user menu

`<NavBar />` MUST render exactly three top-level navigation links on its left side: Home (`/`), Meetings (`/meetings`), Dashboard (`/dashboard`). Settings entry, language toggle, theme toggle, and logout MUST live inside a right-side `<UserMenu />` dropdown. The NavBar MUST NOT render Settings, language, theme, or logout controls directly outside the user menu.

#### Scenario: NavBar exposes home, meetings, and dashboard links

- **WHEN** the home page renders
- **THEN** the NavBar contains exactly three links with test IDs `navbar-home-link`, `navbar-meetings-link`, `navbar-dashboard-link` pointing to `/`, `/meetings`, `/dashboard` respectively

#### Scenario: user menu contains settings, language, theme, logout

- **WHEN** the user opens the user menu
- **THEN** the dropdown contains items with test IDs `usermenu-settings`, `usermenu-locale`, `usermenu-theme`, `usermenu-logout`

##### Example: navbar testid migration

| Old testid                | New testid           | Location after change |
| ------------------------- | -------------------- | --------------------- |
| `navbar-settings-link`    | `usermenu-settings`  | user menu             |
| `navbar-locale-toggle`    | `usermenu-locale`    | user menu             |
| `navbar-theme-toggle`     | `usermenu-theme`     | user menu             |
| `navbar-logout`           | `usermenu-logout`    | user menu             |
| (new)                     | `navbar-home-link`   | navbar                |
| (new)                     | `navbar-meetings-link` | navbar              |
| (new)                     | `navbar-dashboard-link` | navbar             |

### Requirement: Home page SHALL NOT render Slice 1 placeholder content

`<HomePage />` MUST NOT render the legacy stat cards placeholder, the legacy recent meetings list with seeded data, or the Slice 1 backend confirmation debug block (which displayed the raw `/api/health` JSON response). The legacy `Home.tsx` and `home.test.tsx` files MUST be removed from the repository.

#### Scenario: legacy debug block is absent

- **WHEN** the home page renders
- **THEN** no element matching the legacy `data-testid="backend-confirmation"` or equivalent debug block appears in the DOM
