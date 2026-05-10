## ADDED Requirements

### Requirement: The web app uses a single coherent design token set

The web app SHALL define a single design token set in `packages/web/src/index.css` that every route + component consumes via Tailwind utility classes referencing CSS custom properties (e.g. `bg-(--color-primary)`, `text-(--color-foreground)`, `gap-(--spacing-md)`). Token categories required:

- **Color tokens**: at minimum `--color-background`, `--color-foreground`, `--color-card`, `--color-card-foreground`, `--color-primary`, `--color-primary-foreground`, `--color-secondary`, `--color-secondary-foreground`, `--color-muted`, `--color-muted-foreground`, `--color-border`, `--color-input`, `--color-ring`, `--color-destructive`, `--color-destructive-foreground`, plus a 6-step neutral grey scale.
- **Spacing scale**: 8 step scale (e.g. `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`px) — Tailwind's default `1` through `16` mapped to these values. Arbitrary values (`mt-[7px]`, `p-[13px]`) SHALL NOT appear in the codebase.
- **Typography pairing**: one sans-serif family for UI (`Inter` or comparable) and one mono family (`Geist Mono` or comparable). Size scale limited to `xs / sm / base / lg / xl / 2xl` Tailwind tokens.

Hard-coded color hex values, RGB literals, or arbitrary spacing values in component class strings SHALL be considered design-system violations and SHALL be replaced with token references.

#### Scenario: All visible components consume color tokens

- **GIVEN** every route page (`login`, `signup`, `home`, `meetings/list`, `meetings/new`, `meetings/$id`, `meetings/calendar`, `calendar/import`, `totp/enroll`, `totp/verify`)
- **WHEN** a reviewer greps the rendered className strings for hex literals (`#[0-9a-fA-F]{3,8}`) or `rgb(`/`rgba(` calls outside of `index.css`
- **THEN** zero matches SHALL be returned (all colour expressed through `--color-*` tokens)

### Requirement: Card, Button, and Alert components have a fixed variant catalog

The shared shadcn-derived components in `packages/web/src/components/ui/` SHALL expose a fixed catalogue of variants used app-wide:

- **Button**: exactly four variants — `primary` (default), `outline`, `ghost`, `destructive`. All variants SHALL share the same height token (e.g. `h-9`) and consistent horizontal padding. Hover and focus states SHALL be subtle and visually consistent across variants.
- **Card**: a single Card component with subtle border (`border-(--color-border)`), soft shadow (`shadow-sm`), and consistent padding via `CardHeader` / `CardContent` / `CardFooter`. No per-page custom card styling.
- **Alert**: exactly four variants — `destructive`, `warning`, `info`, `success`. Each renders an icon + body; layout consistent across variants.

Pages SHALL use these variants via prop and SHALL NOT override colour or spacing inline. Routes that historically used emoji or arbitrary divs as alerts SHALL migrate to the `Alert` component.

#### Scenario: Buttons across pages share the same height

- **GIVEN** every clickable `<button>` rendered by the app's route pages
- **WHEN** a viewport check inspects their bounding boxes
- **THEN** all primary / outline / ghost / destructive buttons SHALL have the same computed height (within 1px); only `<button data-size="sm">` may differ

### Requirement: Detail page columns mode renders balanced panes

(Cross-references the `meeting-detail-layout` spec's equal-height requirement.) In columns mode the three panes SHALL share equal visible height via the design system's height-constraint utility (`h-[calc(100vh-220px)]` on the grid container plus `h-full` on each pane wrapper). This requirement is enforced at the design-system layer so future panes added to the same grid inherit the same constraint.

#### Scenario: Equal height in columns mode

- **GIVEN** the detail page in columns mode at viewport >=1024px
- **WHEN** the three pane wrappers render
- **THEN** they SHALL have equal `getBoundingClientRect().height` (within 1px tolerance)

### Requirement: All UI strings remain in both locale files (slice-7 round 2 housekeeping)

The deep-equal locale-drift assertion in `packages/web/src/locales/locales.test.ts` SHALL continue to pass after the design system is applied. Any new aria-labels, callouts, helper text, or visible strings introduced by the UI overhaul SHALL appear in both `zh-TW.json` and `en.json`. Component-level Tailwind-only changes (color, spacing, typography) SHALL NOT introduce hard-coded user-facing strings.

#### Scenario: locales.test.ts deep-equal still passes

- **WHEN** `bun test src/locales/locales.test.ts` runs after the slice-7 round-2 design overhaul
- **THEN** the test SHALL pass (zero key drift between zh-TW.json and en.json)
