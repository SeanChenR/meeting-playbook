## MODIFIED Requirements

### Requirement: Design tokens SHALL be expressed as oklch-based CSS variables across two themes

The token catalogue in `packages/web/src/index.css` SHALL declare two complete theme blocks selected via the `data-theme` attribute on `documentElement`. Both themes SHALL be anchored to the Aura colour family (per DESIGN.md §2, derived from `daltonmenezes/aura-theme`):

- `[data-theme="dark"]` (canonical mode per DESIGN.md §1) — primary hue centred on violet (`--primary-hue-dark: 290`), background `oklch(0.17 0.015 290)` (Ink Violet `#15141B`), surface stepped up by lightness, foreground near-white with the same purple tint (`oklch(0.93 0.003 295)`).
- `[data-theme="light"]` (mirror, also applied to bare `:root` so SSR-style flashes default to light) — primary hue centred on violet soft (`--primary-hue: 290`), background `oklch(0.97 0.003 295)` (Mist Bone `#EDECEE`), foreground deep violet-neutral (`oklch(0.20 0.015 290)`).

Both themes MUST share the same set of `--color-*` token names (dark/light parity). Every colour token SHALL be expressed in `oklch(...)` with explicit lightness / chroma / hue; raw hex literals SHALL NOT appear in component class strings or token definitions. Spacing, radius, and typography tokens SHALL be expressed as `--space-N`, `--radius-N`, `--text-N` CSS variables consumed by components.

The token set SHALL include at minimum: `--color-background`, `--color-surface`, `--color-surface-2`, `--color-surface-3`, `--color-foreground`, `--color-muted-foreground`, `--color-subtle-foreground`, `--color-border`, `--color-border-strong`, `--color-primary`, `--color-primary-hover`, `--color-primary-soft`, `--color-primary-foreground`, `--color-secondary`, `--color-secondary-foreground`, `--color-accent`, `--color-accent-foreground`, `--color-success`, `--color-success-soft`, `--color-warning`, `--color-warning-soft`, `--color-danger`, `--color-danger-soft`, `--color-info`, `--color-info-soft`, `--color-me`, `--color-me-soft`, `--color-them`, `--color-them-soft`, `--color-muted`, `--color-recording`.

#### Scenario: Dark theme renders Aura violet on Ink Violet background

- **GIVEN** a fresh browser session with `data-theme="dark"` applied to `documentElement`
- **WHEN** the computed style of `body` is inspected
- **THEN** `background-color` SHALL resolve to `oklch(0.17 0.015 290)` (Ink Violet) AND `--color-primary` SHALL resolve to `oklch(0.65 0.22 290)` (Aura Purple, vibrant)

#### Scenario: Light theme renders Aura violet soft on Mist Bone background

- **GIVEN** a fresh browser session with `data-theme="light"` applied to `documentElement`
- **WHEN** the computed style of `body` is inspected
- **THEN** `background-color` SHALL resolve to `oklch(0.97 0.003 295)` (Mist Bone) AND `--color-primary` SHALL resolve to `oklch(0.50 0.18 290)` (Aura Violet Soft)

#### Scenario: No raw hex colour appears in component class strings

- **GIVEN** the production bundle of `packages/web` after build
- **WHEN** the bundled CSS is scanned for hex colour literals (`#[0-9a-fA-F]{3,8}` patterns) inside component class attributes
- **THEN** the only matches SHALL be inside `index.css` token definitions, inline SVG fill / stroke attributes used by brand logos (Google sign-in icon) or `tag-palette.ts` (an isolated palette domain), CSS mask alpha values (`#000` in `border-beam`), and `rgba()` literals inside `--shadow-*` declarations; no component-level `className` SHALL contain a raw hex outside this explicit allowlist

#### Scenario: Dark and light theme blocks declare identical token keys

- **GIVEN** `packages/web/src/index.css` after this change ships
- **WHEN** an automated parser extracts every `--color-*` declaration name from the `[data-theme="dark"]` and `[data-theme="light"]` (and `:root`) blocks
- **THEN** the symmetric difference of the two key sets SHALL be empty (every token defined in one theme is defined in the other)

### Requirement: TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline

Each rendered transcript chunk in `TranscriptPane` SHALL carry every one of the following visual cues simultaneously (not "any one of"):

1. A 3px solid left border in either `--color-me` (我方) or `--color-them` (對方).
2. A 5-20% tint background in `--color-me-soft` or `--color-them-soft` (mixed via `color-mix(in oklch, ...)` with `--me-tint-alpha` / `--them-tint-alpha` controlling intensity).
3. A speaker dot rendered before the speaker name, filled with the same hue as the left border.
4. The speaker name in semibold (`font-weight: 600`) in `--color-me` or `--color-them`.

The speaker tokens SHALL be anchored to invariant hue families across both themes (per DESIGN.md §2):

- `--color-me` SHALL resolve to a blue hue (hue 220, Glacier Blue family) — `oklch(0.86 0.12 220)` in dark theme, `oklch(0.65 0.10 220)` in light theme.
- `--color-them` SHALL resolve to a magenta hue (hue 320, Magenta Bloom family) — `oklch(0.77 0.22 320)` in dark theme, `oklch(0.55 0.15 320)` in light theme.

`--color-them` SHALL be measurably more saturated than `--color-me` (chroma differential SHALL exceed 0.05 in either theme) so users can scan dialogue ownership at a glance. Speaker tokens SHALL NOT be derived from `--primary-hue` (they are independent of the primary theme hue and remain stable when `--primary-hue` is tuned via design-canvas).

#### Scenario: Counterparty chunk carries all four visual cues in magenta

- **GIVEN** a transcript chunk with `speaker = "counterparty"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the chunk wrapper SHALL have:
  - `border-left-width: 3px` AND `border-left-color` resolving to `oklch(0.55 0.15 320)` (`--color-them`) AND
  - `background-color` resolving to a non-transparent mix of `--color-them-soft` AND
  - a `[data-testid="speaker-dot"]` element with background `--color-them` rendered before the name AND
  - the speaker name element with `font-weight: 600` and colour `--color-them`

#### Scenario: Me chunk uses Glacier Blue in either theme

- **GIVEN** a transcript chunk with `speaker = "me"` rendered in dark theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the same four cues SHALL apply but using `--color-me` resolving to `oklch(0.86 0.12 220)` AND `--color-me-soft` for the background; the visual hierarchy SHALL clearly place 對方 (magenta) as the focal point relative to 我方 (blue)

#### Scenario: Speaker tokens are independent of primary hue

- **GIVEN** the design-canvas runtime knob is used to set `--primary-hue: 200` (an arbitrary blue) on `documentElement`
- **WHEN** the computed style of any rendered transcript chunk is inspected
- **THEN** `--color-me` SHALL still resolve to a blue with hue 220 (NOT 200) AND `--color-them` SHALL still resolve to a magenta with hue 320 — speaker tokens are NOT derived from `--primary-hue`

## ADDED Requirements

### Requirement: `--color-accent` SHALL be an independent magenta token, not a primary alias

The token catalogue in `packages/web/src/index.css` SHALL declare `--color-accent` and `--color-accent-foreground` as standalone oklch values in both theme blocks; the pre-change binding (`--color-accent: var(--color-primary)`) SHALL be removed. The accent token SHALL anchor to the magenta hue family (hue 320, Magenta Bloom / Mauve Soft per DESIGN.md §2):

- Dark theme: `--color-accent: oklch(0.77 0.22 320);` `--color-accent-foreground: oklch(0.17 0.015 290);`
- Light theme: `--color-accent: oklch(0.55 0.15 320);` `--color-accent-foreground: oklch(1 0 0);`

Components consuming `bg-(--color-accent)`, `text-(--color-accent)`, `border-(--color-accent)` SHALL render with magenta in dark theme and mauve in light theme — visibly distinct from `--color-primary` (violet) in either theme.

#### Scenario: Accent renders magenta in dark theme

- **GIVEN** an element with `className="bg-(--color-accent)"` rendered in dark theme
- **WHEN** its computed `background-color` is inspected
- **THEN** the value SHALL resolve to `oklch(0.77 0.22 320)` (Magenta Bloom) AND SHALL NOT equal `--color-primary`

#### Scenario: Accent renders mauve soft in light theme

- **GIVEN** the same element rendered in light theme
- **WHEN** its computed `background-color` is inspected
- **THEN** the value SHALL resolve to `oklch(0.55 0.15 320)` (Mauve Soft) AND SHALL NOT equal `--color-primary`

### Requirement: `--color-info` SHALL be a distinct status token decoupled from speaker me

The token catalogue SHALL declare `--color-info` and `--color-info-soft` in both theme blocks as standalone oklch values anchored to the Glacier Blue / Steel Blue hue family (hue 220). The info token SHALL be value-equal to `--color-me` in initial declaration but SHALL be declared independently so the speaker semantic and the status semantic can diverge in future changes without coupling:

- Dark theme: `--color-info: oklch(0.86 0.12 220);` `--color-info-soft: oklch(0.32 0.06 220);`
- Light theme: `--color-info: oklch(0.65 0.10 220);` `--color-info-soft: oklch(0.92 0.04 220);`

The `--color-info` token SHALL be referenced by status indicators (toast info variant, alert info variant, etc.) and SHALL NOT be referenced by transcript chunk speaker styling (which uses `--color-me` / `--color-them`).

#### Scenario: Info token declared independently from me token

- **GIVEN** `packages/web/src/index.css` after this change ships
- **WHEN** the file is grepped for the two literal declarations `--color-info:` and `--color-me:`
- **THEN** each SHALL appear at least once in both theme blocks AND each SHALL be a literal `oklch(...)` value (NOT a `var(--color-me)` alias)

### Requirement: Default radius scale SHALL be sharp 4 / 6 / 8 / 12

The token catalogue SHALL declare the default radius scale as `--radius-sm: 4px`, `--radius-md: 6px`, `--radius-lg: 8px`, `--radius-xl: 12px`, `--radius-pill: 999px` (per DESIGN.md `rounded` mapping). The `[data-radius="sharp"]` knob SHALL produce a sharper variant (`2px` / `4px` / `6px` / `8px`) and `[data-radius="soft"]` SHALL retain the previous softer scale (`6px` / `12px` / `16px` / `20px`) so existing usage sites remain functional.

#### Scenario: Cards render with 8px radius by default

- **GIVEN** any `<Card>` rendered without `[data-radius]` attribute
- **WHEN** its computed `border-radius` is inspected
- **THEN** the value SHALL resolve to `8px` (`--radius-lg`)

#### Scenario: Buttons render with 4px radius by default

- **GIVEN** any `<Button>` rendered without `[data-radius]` attribute
- **WHEN** its computed `border-radius` is inspected
- **THEN** the value SHALL resolve to `4px` (`--radius-sm`)

### Requirement: Dark theme SHALL favour inset hairlines over drop shadows, light theme SHALL retain soft drop shadows

The token catalogue SHALL declare `--shadow-sm`, `--shadow-md`, `--shadow-lg` per DESIGN.md §1 `shadow` mapping:

- **Dark theme**:
  - `--shadow-sm: none`
  - `--shadow-md: 0 1px 0 rgba(0,0,0,0.3) inset` (inset hairline only)
  - `--shadow-lg: 0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.4)` (1px outline ring + soft drop)
- **Light theme**:
  - `--shadow-sm: 0 1px 2px rgba(20,14,40,0.04)`
  - `--shadow-md: 0 4px 16px rgba(20,14,40,0.06), 0 1px 3px rgba(20,14,40,0.04)`
  - `--shadow-lg: 0 12px 32px rgba(20,14,40,0.1), 0 2px 6px rgba(20,14,40,0.06)`

`--shadow-focus` SHALL remain a 3px oklch primary 25%-opacity ring in both themes. Card / Dialog / Popover surface separation in dark theme SHALL come primarily from the background-vs-surface lightness step, not drop shadows.

`rgba()` inside `--shadow-*` SHALL be a permitted exception to the "no raw rgb/rgba" rule (CSS shadow specification has incomplete oklch support across browsers).

#### Scenario: Dark theme card has no visible drop shadow

- **GIVEN** a `<Card>` rendered with `shadow-sm` Tailwind utility in dark theme
- **WHEN** its computed `box-shadow` is inspected
- **THEN** the value SHALL resolve to `none`

#### Scenario: Light theme card has subtle drop shadow

- **GIVEN** the same `<Card>` rendered with `shadow-sm` Tailwind utility in light theme
- **WHEN** its computed `box-shadow` is inspected
- **THEN** the value SHALL resolve to `0 1px 2px rgba(20, 14, 40, 0.04)` (non-zero alpha drop shadow)

### Requirement: Sonner Toaster SHALL render four semantic colour variants via CSS data-attribute selectors

The web app SHALL provide four semantic Sonner toast variants — `info`, `success`, `warning`, `error` — each mapped to the corresponding Aura semantic token (`--color-info` / `--color-success` / `--color-warning` / `--color-danger`). The mapping SHALL be applied via CSS data-attribute selectors in `packages/web/src/index.css`, overriding Sonner's internal `--normal-bg`, `--normal-border`, `--normal-text` custom properties.

The selector pattern SHALL be:

`[data-sonner-toast][data-type="success"]` sets `--normal-bg: var(--color-success-soft); --normal-border: var(--color-success); --normal-text: var(--color-foreground);`

The same pattern SHALL apply to `data-type="error"` (mapped to `--color-danger` + `--color-danger-soft`), `data-type="warning"` (mapped to `--color-warning` + `--color-warning-soft`), and `data-type="info"` (mapped to `--color-info` + `--color-info-soft`). The `<Toaster>` React component in `packages/web/src/components/ui/sonner.tsx` SHALL NOT have its JSX structure, motion, or behaviour changed in this requirement (deferred to a later phase). Each variant SHALL be visually distinct in both light and dark themes.

#### Scenario: Success toast renders with green accent

- **GIVEN** `toast.success("Saved")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-success-soft` AND its border SHALL resolve to `--color-success`

#### Scenario: Error toast renders with red accent

- **GIVEN** `toast.error("Failed")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-danger-soft` AND its border SHALL resolve to `--color-danger`

#### Scenario: Warning toast renders with orange accent

- **GIVEN** `toast.warning("Quota near limit")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-warning-soft` AND its border SHALL resolve to `--color-warning`

#### Scenario: Info toast renders with blue accent

- **GIVEN** `toast.info("Processing started")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-info-soft` AND its border SHALL resolve to `--color-info`

### Requirement: oklch validation smoke test SHALL guard token format and dark/light parity

The web workspace SHALL ship an automated test (at `packages/web/src/lib/tokens.test.ts` or an equivalent path discoverable by the `bun test` runner) that validates the design token discipline as part of CI. The test SHALL:

1. Read `packages/web/src/index.css` as plain text.
2. Assert that every `--color-*` declaration value matches the pattern `oklch(...)` OR `var(--color-*)` OR a permitted CSS keyword (`none`, `transparent`).
3. Assert dark/light parity: the set of `--color-*` declaration names inside `[data-theme="dark"]` SHALL equal the set inside `[data-theme="light"]` (and `:root`).
4. Scan every file under `packages/web/src/` matching the glob `**/*.{ts,tsx}` (excluding `**/*.test.*`) for raw hex (`#[0-9a-fA-F]{3,8}`), `rgb(`, and `rgba(` occurrences in source code. Matches SHALL be empty unless the file is on the explicit allowlist documented inline in the test with justification:
   - `packages/web/src/lib/tag-palette.ts` — isolated tag palette domain.
   - `packages/web/src/components/magicui/border-beam.tsx` — CSS mask alpha (`#000` in `linear-gradient` inside `WebkitMask`).
   - `packages/web/src/routes/login.tsx` and `packages/web/src/routes/settings/profile.tsx` — Google brand SVG fill values.

Any new allowlist entry added in future PRs SHALL include an inline comment stating the justification; otherwise the test fails.

#### Scenario: All `--color-*` tokens are oklch values

- **GIVEN** `packages/web/src/index.css` after the Aura tokens are applied
- **WHEN** the validation test runs
- **THEN** every line declaring a `--color-` token value SHALL match the permitted-value pattern AND the test SHALL pass

#### Scenario: Dark theme is missing a token that light theme has → test fails

- **GIVEN** a hypothetical edit that removes `--color-info-soft` from the `[data-theme="dark"]` block but leaves it in `[data-theme="light"]`
- **WHEN** the validation test runs
- **THEN** the test SHALL fail with a message that names the missing token

#### Scenario: New component file introduces raw hex without justification → test fails

- **GIVEN** a new file `packages/web/src/components/new-widget.tsx` containing a raw `#ff0000` literal in a className attribute
- **WHEN** the validation test runs
- **THEN** the test SHALL fail with a message that names the offending file and line
