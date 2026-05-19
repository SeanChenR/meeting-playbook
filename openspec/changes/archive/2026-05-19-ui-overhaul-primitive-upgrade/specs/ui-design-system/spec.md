## ADDED Requirements

### Requirement: Dialog and AlertDialog SHALL use animate-ui motion with Aura tokens

The `packages/web/src/components/ui/dialog.tsx` barrel SHALL wrap the animate-ui base dialog primitive. Backdrop SHALL use `var(--color-background)` at 80% opacity with an 8px backdrop blur, content SHALL use `var(--color-surface)` background and `var(--radius-lg)` corner radius. Open / close transitions SHALL use the animate-ui scale + fade motion presets at the default 180ms duration; `prefers-reduced-motion: reduce` SHALL force instant transitions.

Every existing dialog callsite (including the meeting link picker, the playbook regenerate confirmation, and other surfaces opening a Dialog) SHALL import from the `ui/dialog` barrel rather than `@radix-ui/react-dialog` directly. Existing test selectors (`data-testid`, `role="dialog"`, accessible name) SHALL keep resolving so component tests pass without rewrites.

#### Scenario: Opening a Dialog renders animate-ui motion and Aura tokens

- **WHEN** the user opens the meeting link picker dialog
- **THEN** `[role="dialog"]` SHALL mount with computed `background-color` resolving to `var(--color-surface)` AND the backdrop SHALL render `backdrop-filter: blur(8px)` AND the dialog SHALL animate in with scale + fade

#### Scenario: Reduced motion disables dialog animation

- **GIVEN** the user has `prefers-reduced-motion: reduce` set at the OS level
- **WHEN** any Dialog opens
- **THEN** the Dialog SHALL appear at its final state immediately with no scale or fade transition

### Requirement: Popover SHALL ship via a barrel and use animate-ui motion

The web app SHALL add `packages/web/src/components/ui/popover.tsx` exporting `Popover` / `PopoverTrigger` / `PopoverContent` / `PopoverAnchor`, wrapping the animate-ui base popover primitive. Every popover consumer (transcript chunk action menu, speaker color popover, tag picker, transcript chunk row action surface, and any future popover) SHALL import from this barrel; direct imports of `@radix-ui/react-popover` SHALL be removed from feature components.

Popover content SHALL use `var(--color-surface)` background, `var(--color-border)` border, `var(--radius-md)` corner radius, and the animate-ui origin-based scale + opacity entrance. Z-index SHALL keep popover above transcript chunk rows but below modal dialogs.

#### Scenario: Tag picker popover opens via the barrel and reads tokens

- **WHEN** the user clicks the tag picker trigger
- **THEN** a `[role="dialog"]` from the animate-ui popover SHALL mount AND computed `background-color` SHALL resolve to `var(--color-surface)` AND no DOM nodes SHALL originate from `@radix-ui/react-popover` direct imports inside feature components

#### Scenario: Transcript chunk action menu opens via the barrel

- **WHEN** the user opens the action menu for a transcript chunk
- **THEN** the popover content SHALL render with the animate-ui scale entrance AND the trigger SHALL retain its existing `data-testid` so e2e selectors continue to resolve

### Requirement: Tooltip SHALL wrap every hover-info button across the app

`packages/web/src/components/ui/tooltip.tsx` SHALL wrap the animate-ui primitives/animate/tooltip and SHALL be applied to every icon-only button, badge, or hover-info control that conveys supplementary information. The audit MUST cover at least: the recording badge, the dual-channel capture indicator, the rerun transcript button, the theme toggle button, and the locale toggle button. Tooltip background SHALL use `var(--color-foreground)` and tooltip text SHALL use `var(--color-background)` (inverse) per DESIGN.md §4. Every tooltip content string SHALL be backed by an i18n key with parity in both `zh-TW.json` and `en.json`.

#### Scenario: Icon-only buttons surface a tooltip on hover

- **WHEN** the user hovers any icon-only button across the audited surfaces (recording badge, capture indicator, rerun button, theme toggle, locale toggle, and any other listed in the audit task)
- **THEN** an animate-ui tooltip SHALL render with text resolved from a `t("ui.tooltip.*")` key AND the tooltip SHALL use inverse colours (foreground background, background text)

#### Scenario: Tooltip strings exist in both locales

- **WHEN** `locales.test.ts` runs the deep-equal parity guard
- **THEN** every `ui.tooltip.*` key SHALL be present in both `zh-TW.json` and `en.json` with equal structure

### Requirement: Determinate Progress SHALL use animate-ui base progress

The web app SHALL add `packages/web/src/components/ui/progress.tsx` wrapping the animate-ui base progress primitive. The bar fill SHALL use `var(--color-primary)`, the track SHALL use `var(--color-surface-2)`, the height SHALL be 4px by default, and corner radius SHALL be `var(--radius-pill)`. The component SHALL accept `value` (0..100) and an `aria-label` prop. Indeterminate behavior SHALL be rejected for this component; long-running operations without a known total SHALL use the indeterminate Loading component instead.

#### Scenario: Progress renders fill proportional to value

- **WHEN** `<Progress value={42} aria-label="Generating playbook" />` mounts
- **THEN** the rendered bar SHALL have computed width near 42% of the track AND `[role="progressbar"]` SHALL carry `aria-valuenow="42"` AND the fill background SHALL resolve to `var(--color-primary)`

### Requirement: Indeterminate Loading SHALL be a ported uiverse animation in Aura purple

The web app SHALL add `packages/web/src/components/ui/loading.tsx`, a React + Tailwind port of `https://uiverse.io/gustavofusco/rare-pug-90`. The animation SHALL run on `var(--color-primary)` (Aura purple) rather than the original colours. The source file SHALL include a top-of-file comment stating `Source: https://uiverse.io/gustavofusco/rare-pug-90 (CC0)` for license attribution. Sizes `sm` / `md` / `lg` SHALL be exposed via a `size` prop. The component SHALL respect `prefers-reduced-motion: reduce` by rendering a static dot or `Skeleton` fallback with no animation.

#### Scenario: Loading respects reduced motion

- **GIVEN** the user has `prefers-reduced-motion: reduce` set
- **WHEN** `<Loading aria-label="Loading transcript" />` mounts
- **THEN** the DOM SHALL render the fallback static element with no animation styles applied AND the accessible name SHALL still be exposed via the `aria-label`

#### Scenario: Loading uses Aura purple

- **WHEN** the component mounts in the default dark theme without reduced motion
- **THEN** the computed colour of the animated dots SHALL resolve to `var(--color-primary)` and no raw hex literal SHALL appear in the component class strings

### Requirement: Theme toggler SHALL be the magicui animated reveal switch limited to two states

`packages/web/src/components/theme-toggle.tsx` SHALL be replaced by an implementation using `https://magicui.design/docs/components/animated-theme-toggler`. The toggle UI SHALL expose only `dark` and `light` states; the `system` state SHALL no longer be reachable through the toggle (fresh sessions SHALL still fall back to `prefers-color-scheme` until the first click). The button SHALL carry an `aria-label` resolved from `t("ui.themeToggle.label")` and the action labels SHALL come from `t("ui.themeToggle.toLight")` / `t("ui.themeToggle.toDark")`. Click SHALL trigger the circular reveal animation; reduced motion SHALL collapse the reveal into an instant swap.

`ThemeProvider`'s `theme` type SHALL remain `"light" | "dark" | "system"` to keep persistence backward-compatible; only the toggle UI surface SHALL be reduced to two states.

#### Scenario: Clicking the toggle alternates between dark and light only

- **GIVEN** the application is in the default dark theme after a fresh load
- **WHEN** the user clicks the theme toggle once and then again
- **THEN** `documentElement` `data-theme` SHALL change to `"light"` and then back to `"dark"` AND `localStorage.mp-theme` SHALL store the explicit choice (no `"system"` value SHALL be written by the toggle)

#### Scenario: Theme toggle accessible name is localised

- **WHEN** the toggle renders in the en locale and then in the zh-TW locale
- **THEN** the button's accessible name SHALL resolve to the value of `ui.themeToggle.label` from the active locale file AND both `zh-TW.json` and `en.json` SHALL contain that key

### Requirement: Toast SHALL expose four semantic variants tied to Aura semantic tokens

`packages/web/src/components/ui/sonner.tsx` SHALL surface four semantic toast variants — `info`, `success`, `warning`, `error` — each callable as `toast.info(...)` / `toast.success(...)` / `toast.warning(...)` / `toast.error(...)`. Each variant SHALL render with a left-edge stripe whose colour resolves to `var(--color-info)`, `var(--color-success)`, `var(--color-warning)`, or `var(--color-danger)` respectively. Every existing direct `toast(...)` callsite in feature components (export meeting button, playbook pane, offline ingest upload dialog, and any others) SHALL be migrated to the appropriate semantic helper. The legacy `toast(...)` passthrough SHALL remain callable to avoid build breakage during migration but SHALL render with no stripe.

JSX wrappers `<ToastInfo>` / `<ToastSuccess>` / `<ToastWarning>` / `<ToastError>` SHALL be provided in `packages/web/src/components/ui/toast-variants.tsx` for declarative callsites. Each variant SHALL carry an `aria-label` resolved from `t("ui.toast.<variant>.label")` (info / success / warning / error), with parity in both locale files.

#### Scenario: Success toast renders the success stripe and aria-label

- **WHEN** a feature component calls `toast.success(t("playbook.regen.done.body"))`
- **THEN** the rendered toast node SHALL carry `data-type="success"` AND a visible stripe whose computed colour resolves to `var(--color-success)` AND its accessible name SHALL resolve to the `ui.toast.success.label` key from the active locale

#### Scenario: Error toast renders the danger stripe

- **WHEN** the export meeting mutation fails and the component calls `toast.error(...)`
- **THEN** the rendered toast SHALL carry `data-type="error"` AND a stripe whose computed colour resolves to `var(--color-danger)`

#### Scenario: Toast locale parity holds

- **WHEN** `locales.test.ts` runs the deep-equal guard
- **THEN** `ui.toast.info.label`, `ui.toast.success.label`, `ui.toast.warning.label`, and `ui.toast.error.label` SHALL exist in both `zh-TW.json` and `en.json`

### Requirement: Date selection in meeting forms SHALL use the Aura calendar picker

`packages/web/src/components/ui/calendar.tsx` SHALL ship a wrapper over `https://www.shadcnblocks.com/component/calendar/calendar-standard-3` styled with Aura tokens (`--color-primary` for selected day, `--color-surface` for the panel, `--color-border` for cell borders, `--radius-md` for the panel corners). The source file SHALL include a top-of-file comment stating `Source: https://www.shadcnblocks.com/component/calendar/calendar-standard-3`.

The meeting edit form and `routes/meetings/new.tsx` SHALL replace each `<input type="datetime-local">` with the combination of `<Calendar />` (date) and `<Input type="time" />` (time). The form submit handler SHALL combine the date and time into an ISO datetime string so the backend payload shape remains unchanged. The calendar SHALL expose `aria-label`, prev / next month buttons, and a "today" shortcut, all backed by i18n keys (`ui.calendar.openPicker`, `ui.calendar.clear`, `ui.calendar.today`).

#### Scenario: Selecting a date and time produces the same ISO submit payload

- **GIVEN** the user opens the meeting edit form with `scheduled_start_at = "2026-05-20T14:30:00+08:00"`
- **WHEN** the user selects date `2026-05-22` via the calendar AND types time `09:00` into the time input AND submits the form
- **THEN** the form SHALL send `scheduled_start_at = "2026-05-22T09:00:00+08:00"` (or equivalent ISO datetime) to the backend AND the backend payload shape SHALL be unchanged from the prior `datetime-local` behaviour

#### Scenario: Calendar locale strings parity

- **WHEN** `locales.test.ts` runs the parity guard
- **THEN** `ui.calendar.openPicker`, `ui.calendar.clear`, and `ui.calendar.today` SHALL exist in both `zh-TW.json` and `en.json`

### Requirement: Vendor install spike SHALL gate the production primitive work

Before any feature code in this change is committed to a production branch, a Task 0 spike SHALL verify that the `@animate-ui` base dialog, the magicui animated theme toggler, and the shadcnblocks `calendar-standard-3` snippet all install via the shadcn-compatible CLI without peer dependency conflicts. The spike SHALL confirm that `bun run build`, `bunx tsc --noEmit`, and the dev server start all pass with the vendor packages added, and that Tailwind v4 token override syntax (`bg-(--color-surface)` and equivalents) resolves correctly inside the vendor components.

If the spike surfaces conflicts (peer dep clashes, Tailwind v4 incompatibility, or a license header indicating a shadcnblocks Pro tier), the change SHALL pause and the conflict SHALL be reported back before production work continues.

#### Scenario: Spike succeeds and production tasks proceed

- **WHEN** the spike branch installs the three vendor packages AND `bun run build`, `bunx tsc --noEmit`, and the dev server start all return success
- **THEN** the spike SHALL be marked complete and the production primitive tasks SHALL be allowed to begin

#### Scenario: Spike fails and production work pauses

- **WHEN** the spike branch surfaces any peer dependency conflict OR a license incompatibility OR a build failure attributable to the new vendor packages
- **THEN** production tasks SHALL NOT begin AND the conflict SHALL be surfaced to the change owner for a decision (alternative vendor, fallback to existing primitive, or escalate)

##### Example: shadcnblocks calendar block is gated behind a paid tier

- **GIVEN** the spike has installed `@animate-ui` base dialog (no conflict) AND magicui animated-theme-toggler (no conflict) AND attempts to fetch shadcnblocks `calendar-standard-3`
- **WHEN** the shadcnblocks page license header reads "Pro tier, paid license required"
- **THEN** the spike SHALL stop before adding the snippet, the change owner SHALL be notified, and the production primitive tasks SHALL remain blocked until either (a) the calendar is replaced by the shadcn-internal `calendar` component or (b) the change owner approves the license cost
