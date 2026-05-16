## ADDED Requirements

### Requirement: SettingsLayout provides a dual-column shell with a persistent left sub-nav

The web client SHALL provide a `<SettingsLayout>` component that renders a two-column layout: a persistent left navigation rail (the **settings sub-nav**) and a right content pane (`<Outlet />`). The layout MUST be registered as a TanStack Router layout route at the URL path `/settings`, and ALL settings sub-routes MUST nest under this layout route so the sub-nav does not unmount when switching between sub-routes. The layout MUST be reachable only by authenticated users; unauthenticated access SHALL follow the existing gateway auth guard.

#### Scenario: SettingsLayout renders the sub-nav and an outlet

- **WHEN** an authenticated user navigates to any `/settings/*` URL
- **THEN** the page SHALL render the settings sub-nav as a left rail AND a content pane on the right that displays the matched sub-route component

#### Scenario: Sub-nav persists across sub-route switches

- **GIVEN** the user is on `/settings/profile`
- **WHEN** the user clicks the "Voice" item in the sub-nav
- **THEN** the URL SHALL update to `/settings/voice` AND the sub-nav component instance MUST NOT unmount between the two renders

### Requirement: Settings sub-nav lists exactly seven sub-routes in a fixed order

The settings sub-nav SHALL list exactly the following seven items in this order: profile, security, voice, tags, integrations, preferences, data. Each item MUST be a link that navigates to the corresponding sub-route (`/settings/<item>`). The currently active item MUST be marked with `aria-current="page"`. Each item SHALL display a localized label sourced from the `settings.nav.<item>` i18n key in both `zh-TW.json` and `en.json`.

#### Scenario: Sub-nav lists seven items in order

- **WHEN** the settings sub-nav renders
- **THEN** it SHALL contain exactly seven navigation links in this order: profile, security, voice, tags, integrations, preferences, data

##### Example: sub-nav items in exact rendered order

| Position | i18n key | Target route |
| ----- | --------------- | ----- |
| 1 | `settings.nav.profile` | `/settings/profile` |
| 2 | `settings.nav.security` | `/settings/security` |
| 3 | `settings.nav.voice` | `/settings/voice` |
| 4 | `settings.nav.tags` | `/settings/tags` |
| 5 | `settings.nav.integrations` | `/settings/integrations` |
| 6 | `settings.nav.preferences` | `/settings/preferences` |
| 7 | `settings.nav.data` | `/settings/data` |

#### Scenario: Active item is marked

- **GIVEN** the user is on `/settings/security`
- **WHEN** the sub-nav renders
- **THEN** the "security" link SHALL have `aria-current="page"` AND all other links SHALL NOT have `aria-current="page"`

### Requirement: /settings index redirects to /settings/profile

The web client SHALL register an index route under the settings layout that redirects the bare `/settings` URL (with or without a trailing slash) to `/settings/profile`. The redirect MUST happen in `beforeLoad` so no intermediate page renders.

#### Scenario: Bare /settings redirects to profile

- **WHEN** a user navigates to `/settings`
- **THEN** the browser SHALL be redirected to `/settings/profile` AND the redirect MUST NOT render an intermediate blank or loading page

### Requirement: /settings/profile displays the current Better Auth session user

The `/settings/profile` sub-route SHALL render a display-only view of the current Better Auth session user, showing the user's name, email, and avatar image. The view MUST NOT provide editing controls in this capability; if no avatar is available, the view SHALL render a fallback localized via `settings.profile.avatar_alt`. The data source MUST be the existing Better Auth session client; no new backend endpoint is introduced.

#### Scenario: Profile shows name, email, and avatar

- **GIVEN** an authenticated session with `user.name = "Sean"`, `user.email = "sean@example.com"`, and a non-null `user.image`
- **WHEN** the user navigates to `/settings/profile`
- **THEN** the page SHALL render the text "Sean", the text "sean@example.com", and an `<img>` element whose `src` attribute equals `user.image`

### Requirement: /settings/security wraps existing TOTP controls

The `/settings/security` sub-route SHALL render the existing TOTP enrollment and management controls inside the `<SettingsLayout>` shell. The behavior of TOTP enrollment, verification, and unenrollment MUST remain identical to the pre-slice behavior; this requirement covers placement only, not behavior changes.

#### Scenario: Security sub-route renders TOTP status

- **WHEN** an authenticated user navigates to `/settings/security`
- **THEN** the page SHALL display the user's current TOTP enrollment status AND provide a link or button to enroll/unenroll using the existing TOTP UI components

### Requirement: /settings/voice nests Slice 13 voice enrollment under the settings layout

The `/settings/voice` sub-route SHALL render the existing Slice 13 voice enrollment UI nested under `<SettingsLayout>`. The URL path `/settings/voice` MUST remain stable (backward compatible with Slice 13 bookmarks). The voice enrollment component's props, behavior, and i18n keys MUST NOT change in this capability.

#### Scenario: /settings/voice URL is preserved

- **WHEN** a user navigates to `/settings/voice`
- **THEN** the URL bar SHALL display `/settings/voice` AND the page SHALL render the Slice 13 voice enrollment UI inside the settings sub-nav shell

### Requirement: /settings/tags nests Slice 17 tag management under the settings layout

The `/settings/tags` sub-route SHALL render the existing Slice 17 tag management UI nested under `<SettingsLayout>`. The URL path `/settings/tags` MUST remain stable. The tag management component's props, behavior, and i18n keys MUST NOT change in this capability.

#### Scenario: /settings/tags URL is preserved

- **WHEN** a user navigates to `/settings/tags`
- **THEN** the URL bar SHALL display `/settings/tags` AND the page SHALL render the Slice 17 tag management UI inside the settings sub-nav shell

### Requirement: /settings/integrations renders the calendar connection panel

The `/settings/integrations` sub-route SHALL render the Google Calendar connection-status UI previously hosted at `/calendar/import`. The connection panel MUST be extracted into a reusable component so that the legacy `/calendar/import` route and the new `/settings/integrations` route can share the same implementation without duplication. The cross-spec contract for moving the connection UI is captured separately by the `calendar-integration` capability.

#### Scenario: Integrations sub-route renders the calendar connection panel

- **WHEN** an authenticated user navigates to `/settings/integrations`
- **THEN** the page SHALL render the same Google Calendar connection-status UI (connect button when disconnected, upcoming events list when connected) as was previously rendered at `/calendar/import`

### Requirement: /settings/preferences exposes language, theme, and default ASR provider fields

The `/settings/preferences` sub-route SHALL display three labeled fields: language, theme, and default ASR provider. Language and theme MUST be interactive controls that invoke the existing i18n and theme switchers respectively. The default ASR provider field MUST be display-only in this capability and MUST be visually marked as not-yet-editable (for example via a "coming soon" indicator) so users do not assume it is broken. All three labels MUST be localized via the `settings.preferences.*` i18n namespace in both `zh-TW.json` and `en.json`.

#### Scenario: Preferences renders three fields

- **WHEN** an authenticated user navigates to `/settings/preferences`
- **THEN** the page SHALL render exactly three labeled fields in this order: language, theme, default ASR provider

#### Scenario: ASR provider field is read-only with a coming-soon indicator

- **WHEN** the preferences page renders the default ASR provider field
- **THEN** the field MUST NOT expose an enabled control that submits changes AND MUST display a "coming soon" indicator (badge, helper text, or equivalent) localized from the `settings.preferences` namespace

### Requirement: /settings/data exposes recording window, export-all, and delete-account placeholders

The `/settings/data` sub-route SHALL display three sections: the recording window (showing the value `30 days` as read-only text), an "Export all data" button, and a "Delete account" button. Pressing either button MUST display a localized "coming soon" dialog or notice and MUST NOT trigger any backend mutation. All labels MUST be localized via the `settings.data.*` i18n namespace in both `zh-TW.json` and `en.json`.

#### Scenario: Data sub-route renders recording window value

- **WHEN** an authenticated user navigates to `/settings/data`
- **THEN** the page SHALL display the text "30 days" (or its localized equivalent via `settings.data.recording_window_value`) as the recording window value AND the value MUST be rendered as plain text, not as an editable control

#### Scenario: Export all data button shows coming-soon dialog

- **GIVEN** the user is on `/settings/data`
- **WHEN** the user clicks the "Export all data" button
- **THEN** a coming-soon dialog or notice SHALL appear AND no network request SHALL be issued to any export endpoint

#### Scenario: Delete account button shows coming-soon dialog

- **GIVEN** the user is on `/settings/data`
- **WHEN** the user clicks the "Delete account" button
- **THEN** a coming-soon dialog or notice SHALL appear AND no network request SHALL be issued to any account-deletion endpoint

### Requirement: User menu in the navbar provides a Settings entry

The application navbar's user menu (the right-aligned dropdown anchored on the avatar) SHALL include a "Settings" menu item that navigates to `/settings/profile`. The label MUST be localized via the `settings.nav.menu_entry` i18n key in both `zh-TW.json` and `en.json`. The menu item MUST be visible to all authenticated users.

#### Scenario: User menu exposes Settings entry

- **GIVEN** an authenticated user opens the user menu in the navbar
- **WHEN** the menu is open
- **THEN** the menu SHALL contain a "Settings" item whose target navigates to `/settings/profile`

### Requirement: Settings sub-nav and content i18n strings are present in both locales

Every new user-visible string added by the settings shell — including sub-nav labels (`settings.nav.*`), section titles (`settings.<section>.title`), and content for the preferences and data sections — SHALL be present in both `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` simultaneously. Drift between the two locale files for any `settings.*` key MUST cause the existing locale-equality test to fail.

#### Scenario: Locale files are in sync for settings strings

- **WHEN** the `settings.*` namespace is added or modified in either locale file
- **THEN** the same set of keys MUST exist in both `zh-TW.json` and `en.json` AND the existing deep-equal locale test SHALL pass
