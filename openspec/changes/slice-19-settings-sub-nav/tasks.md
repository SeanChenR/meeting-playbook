<!--
Tracer-bullet vertical slice for `slice-19-settings-sub-nav`. Each task is a
red-green-refactor unit. `[P]` marks tasks that operate on disjoint files
with no shared dependency on another pending task in the same group and can
therefore run in parallel.

Apply blocks on Slice 18 (Issue #26) being archived; the first task is a
gate that surfaces this dependency before any code work begins.
-->

## 1. 前置與 i18n 骨架

- [ ] 1.1 Gate apply on Slice 18 (Issue #26) being archived — confirm `slice-18-*` is in `openspec/changes/archive/`. Behavior: apply must not proceed unless S18 is archived. Verification: `ls openspec/changes/archive/ | grep slice-18` returns a directory; if empty, stop and surface the missing dependency.
- [x] 1.2 Implement Decision 4：i18n namespace 分組 — add the `settings` namespace skeleton (`nav.*`, `profile.*`, `security.*`, `integrations.*`, `preferences.*`, `data.*`, plus `nav.menu_entry`) to both `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json`. Behavior: the existing locale deep-equal test continues to pass with the new keys present in both locale files. Verification: `bun --filter @meeting-playbook/web test -- locales` exits 0.

## 2. SettingsLayout shell + sub-nav

- [x] 2.1 [P] Implement Decision 3：sub-nav 用 shadcn / animate-ui 既有元件，不引入新依賴 — build `<SettingsSubNav />` so it delivers the seven-item ordered nav with `aria-current="page"` on the active item, per the **Settings sub-nav lists exactly seven sub-routes in a fixed order** requirement, using only existing shadcn / animate-ui primitives (no new npm dependency). Verification: new `packages/web/src/components/settings/sub-nav.test.tsx` covers the order, labels (from `settings.nav.*`), and active-state behavior in red → green → refactor order; `package.json` diff shows no new dependency added.
- [x] 2.2 Implement Decision 1：採用 TanStack Router 的 layout route，而非每個 sub-route 自帶 shell — build `<SettingsLayout />` rendering a dual-column shell (left sub-nav + right `<Outlet />`) per the **SettingsLayout provides a dual-column shell with a persistent left sub-nav** requirement, registered as a TanStack Router layout route so the sub-nav does not unmount across sub-route switches. Verification: new `packages/web/src/routes/settings/layout.test.tsx` asserts a single sub-nav component instance survives an `<Outlet />` swap via a memory router.

## 3. Route tree: layout route, index redirect, calendar redirect

- [x] 3.1 Register `settingsLayoutRoute` (path `/settings`, component `SettingsLayout`) in `packages/web/src/route-tree.tsx` and migrate `settingsVoiceRoute` to be a child route with relative path `voice`. Behavior: `/settings/voice` URL stays stable, page renders inside the new shell, satisfying the **/settings/voice nests Slice 13 voice enrollment under the settings layout** requirement. Verification: existing `packages/web/src/routes/settings/voice.test.tsx` stays green; any DOM-coupled assertions are stabilized via `getByRole` queries.
- [x] 3.2 Add a settings index route that redirects `/settings` to `/settings/profile` via `beforeLoad → throw redirect(...)` per the **/settings index redirects to /settings/profile** requirement. Verification: new `packages/web/src/routes/settings/redirect.test.tsx` asserts that a memory-router navigation to `/settings` resolves to `/settings/profile` with no intermediate render.
- [ ] 3.3 Implement Decision 2：`/calendar/import` 改 redirect，內容元件 inline 進 `/settings/integrations` — replace `calendarImportRoute`'s component with a `beforeLoad → throw redirect({ to: "/settings/integrations" })`, satisfying the **Calendar import lives at /calendar/import to disambiguate from the meetings calendar view** modified requirement's redirect scenario. Verification: `packages/web/src/routes/settings/redirect.test.tsx` asserts `/calendar/import` ends at `/settings/integrations` with no intermediate render.

## 4. Calendar panel extraction + integrations sub-route

- [x] 4.1 Extract `<CalendarIntegrationPanel />` as a reusable component from `packages/web/src/routes/calendar/upcoming.tsx`, keeping the existing `calendar.*` i18n keys and connection/upcoming-events logic unchanged. Behavior: the panel can be rendered standalone without the old route wrapper. Verification: new `packages/web/src/components/calendar/calendar-integration-panel.test.tsx` red → green for the three connection states (disconnected prompt, connected with empty events, connected with events).
- [x] 4.2 `/settings/integrations` sub-route renders `<CalendarIntegrationPanel />` inside the settings shell per the **/settings/integrations renders the calendar connection panel** requirement. Verification: new `packages/web/src/routes/settings/integrations.test.tsx` asserts the connection panel and sub-nav coexist.
- [ ] 4.3 Update every in-app link that previously pointed to `/calendar/import` (home, meetings list, navbar, any user menu) to point to `/settings/integrations`, satisfying the **Calendar import lives at /calendar/import to disambiguate from the meetings calendar view** Scenario "Internal navigation uses the new path". Verification: `bun --filter @meeting-playbook/web test` is green AND a project-wide grep `rg 'to="/calendar/import"' packages/web/src` returns zero hits.

## 5. Profile, Security, Voice/Tags wrap, Preferences, Data sub-routes

- [x] 5.1 [P] `/settings/profile` displays the Better Auth session user's name, email, and avatar (read-only) per the **/settings/profile displays the current Better Auth session user** requirement. Verification: new `packages/web/src/routes/settings/profile.test.tsx` asserts the three fields render from a mocked session.
- [x] 5.2 [P] `/settings/security` wraps existing TOTP enrollment status and entry controls inside the settings shell per the **/settings/security wraps existing TOTP controls** requirement. Verification: new `packages/web/src/routes/settings/security.test.tsx` asserts the TOTP-status text and the existing enroll/unenroll link/button render unchanged.
- [ ] 5.3 [P] Migrate `settingsTagsRoute` (if present from Slice 17) to nest under `settingsLayoutRoute` with relative path `tags`, preserving the `/settings/tags` URL and Slice 17 behavior per the **/settings/tags nests Slice 17 tag management under the settings layout** requirement. Verification: any existing tags route test stays green; if no test exists yet, add `packages/web/src/routes/settings/tags-shell.test.tsx` that asserts the tag UI renders inside the sub-nav shell.
- [x] 5.4 [P] Implement Decision 5：preferences sub-route 的三個欄位只做 UI，不持久化 — `/settings/preferences` renders language, theme, and read-only default ASR provider fields with a coming-soon indicator on the ASR field, per the **/settings/preferences exposes language, theme, and default ASR provider fields** requirement. Verification: new `packages/web/src/routes/settings/preferences.test.tsx` asserts the three fields, that language and theme controls invoke the existing switchers, and that the ASR provider field renders the localized read-only badge.
- [x] 5.5 [P] Implement Decision 6：data sub-route 的兩個按鈕在本 slice 是「展示 + coming soon」 — `/settings/data` renders the read-only `30 days` recording window value plus Export-all and Delete-account buttons that open a localized coming-soon dialog with no network request, per the **/settings/data exposes recording window, export-all, and delete-account placeholders** requirement. Verification: new `packages/web/src/routes/settings/data.test.tsx` asserts the recording window text, both buttons, the dialog open behavior, and that no `fetch` is invoked on click (use a spy).

## 6. Navbar user menu entry

- [x] 6.1 The navbar user-menu dropdown exposes a "Settings" item that navigates to `/settings/profile` per the **User menu in the navbar provides a Settings entry** requirement, using the `settings.nav.menu_entry` i18n key. Verification: extend (or add) `packages/web/src/components/navbar.test.tsx` to open the user menu, find the "Settings" item, and assert its `to` prop equals `/settings/profile`.

## 7. i18n closure + verification loop

- [x] 7.1 Fill in all remaining `settings.*` strings introduced by tasks 5.1–5.5 and 6.1 in both `zh-TW.json` and `en.json` per the **Settings sub-nav and content i18n strings are present in both locales** requirement. Verification: `packages/web/src/locales/locales.test.tsx` (deep-equal locale-sync) passes with zero key drift.
- [ ] 7.2 Full web-package verification gate — run `bun --filter @meeting-playbook/web lint` and `bun --filter @meeting-playbook/web test`; both must exit 0 with the new sub-route tests and the existing voice/tags/calendar tests all green. Verification: terminal output of both commands archived in the apply session log.
- [ ] 7.3 Manual acceptance walkthrough per the Implementation Contract's nine end-user observable behaviors (Settings menu entry → profile → sub-nav swap → integrations → `/calendar/import` redirect → voice URL stable → tags URL stable → preferences fields → data buttons coming-soon) in both zh-TW and en. Verification: human checkmark on each of the nine items recorded in the apply session log.
