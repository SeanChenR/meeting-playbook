## ADDED Requirements

### Requirement: Design tokens SHALL be expressed as oklch-based CSS variables across two themes

The token catalogue in `packages/web/src/index.css` SHALL declare two complete theme blocks selected via the `data-theme` attribute on `documentElement`:

- `[data-theme="light"]` (default, also applied to bare `:root` so SSR-style flashes default to light) — primary hue centred on violet (`--primary-hue: 280`), surface near-white with subtle violet tint, foreground deep neutral.
- `[data-theme="dark"]` — primary hue centred on warm orange (`--primary-hue-dark: 50`), surface deep neutral with subtle warm tint, foreground near-white.

Every colour token SHALL be expressed in `oklch(...)` with explicit lightness / chroma / hue; raw hex literals SHALL NOT appear in component class strings or token definitions. Spacing, radius, and typography tokens SHALL be expressed as `--space-N`, `--radius-N`, `--text-N` CSS variables consumed by components.

#### Scenario: Light theme is applied on first render without user preference

- **GIVEN** a fresh browser session with no `mp-theme` value in `localStorage` AND `prefers-color-scheme: light`
- **WHEN** the `ThemeProvider` mounts
- **THEN** `documentElement` SHALL gain `data-theme="light"` AND `--color-primary` SHALL resolve to an oklch value with hue near 280

#### Scenario: Dark theme is applied when system prefers dark

- **GIVEN** a fresh browser session with no `mp-theme` value AND `prefers-color-scheme: dark`
- **WHEN** the `ThemeProvider` mounts
- **THEN** `documentElement` SHALL gain `data-theme="dark"` AND `--color-primary` SHALL resolve to an oklch value with hue near 50

#### Scenario: No raw hex colour appears in component class strings

- **GIVEN** the production bundle of `packages/web` after build
- **WHEN** the bundled CSS is scanned for hex colour literals (`#[0-9a-fA-F]{3,8}` patterns) inside component class attributes
- **THEN** the only matches SHALL be inside `index.css` token definitions or inline SVG fill / stroke attributes used by lucide icons; no component-level `className` SHALL contain a raw hex

### Requirement: ThemeProvider SHALL persist user choice and expose a typed Context

The web app SHALL provide a `ThemeProvider` React component (in `packages/web/src/lib/theme-provider.tsx`) that wraps `App` and exposes a `useTheme()` hook returning `{ theme, resolved, setTheme }`. `theme` is the raw user preference (`"light" | "dark" | "system"`); `resolved` is the effective theme (`"light" | "dark"`) after collapsing `"system"` against `prefers-color-scheme`. `setTheme` SHALL persist the preference to `localStorage.mp-theme`.

The `theme-toggle` component (in `packages/web/src/components/theme-toggle.tsx`) SHALL render in the `NavBar` right-side cluster and SHALL cycle through `light` → `dark` → `system` on click.

#### Scenario: Toggling theme persists across reload

- **GIVEN** the user is on any `ProtectedShell` route with `data-theme="light"`
- **WHEN** the user clicks the theme toggle until `data-theme="dark"` is applied AND reloads the browser
- **THEN** on reload `localStorage.mp-theme` SHALL equal `"dark"` AND `documentElement` SHALL re-mount with `data-theme="dark"` immediately (no flash of light)

#### Scenario: System preference change updates resolved theme when theme="system"

- **GIVEN** the user has set `theme = "system"` AND the OS is currently `prefers-color-scheme: light`
- **WHEN** the OS preference changes to `dark` while the app is open
- **THEN** `documentElement` `data-theme` SHALL update to `"dark"` without page reload (via `matchMedia('(prefers-color-scheme: dark)').addEventListener`)

#### Scenario: Corrupted localStorage falls back to system

- **GIVEN** `localStorage.mp-theme` holds an invalid value like `"purple"` or random garbage
- **WHEN** `ThemeProvider` mounts
- **THEN** the provider SHALL fall back to `theme = "system"` AND SHALL NOT throw

### Requirement: Five shadcn primitives SHALL be added with consistent file layout

The web app SHALL gain the following primitives under `packages/web/src/components/ui/`, each a thin wrapper over the matching radix headless primitive styled with Tailwind v4 utility classes consuming the token CSS variables:

- `select.tsx` — wraps `@radix-ui/react-select`; replaces every native `<select>` in feature components (notably `AsrProviderSelector`).
- `dropdown-menu.tsx` — wraps `@radix-ui/react-dropdown-menu`; used by `theme-toggle` and `locale-toggle`.
- `tooltip.tsx` — wraps `@radix-ui/react-tooltip`; used by `RecordingBadge` dot and `CaptureIndicator` status icons.
- `skeleton.tsx` — pure CSS shimmer (no radix dependency); replaces ad-hoc loading placeholders.
- `sonner.tsx` — wraps `sonner` toast library; mounted once by `ProtectedShell`. Replaces every in-component inline error `<span>` that currently surfaces mutation errors.

Each primitive SHALL be unit-tested with a smoke test asserting at least mount + visible-by-default behaviour. None SHALL use inline `style={{...}}` props for cosmetic styling (lucide icon sizing inline is allowed).

#### Scenario: AsrProviderSelector uses shadcn Select after the overhaul

- **GIVEN** the meeting detail page after this change ships
- **WHEN** the `AsrProviderSelector` is rendered
- **THEN** the DOM SHALL contain a `[role="combobox"]` from radix-select (not a native `<select>` element) AND `data-testid="asr-provider-selector"` SHALL still resolve to the trigger button so the existing component test keeps working

#### Scenario: Mutation errors surface via Sonner toast, not inline span

- **GIVEN** the `RerunButton` POST mutation fails with a `RerunApiError`
- **WHEN** the mutation `onError` handler fires
- **THEN** a toast SHALL appear via `sonner` carrying the localised error message AND no inline `<span class="...destructive...">` SHALL be rendered next to the button

### Requirement: TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline

Each rendered transcript chunk in `TranscriptPane` SHALL carry every one of the following visual cues simultaneously (not "any one of"):

1. A 3px solid left border in either `--color-me` (我方) or `--color-them` (對方).
2. A 5-20% tint background in `--color-me-soft` or `--color-them-soft` (mixed via `color-mix(in oklch, ...)` with `--me-tint-alpha` / `--them-tint-alpha` controlling intensity).
3. A speaker dot rendered before the speaker name, filled with the same hue as the left border.
4. The speaker name in semibold (`font-weight: 600`) in `--color-me` or `--color-them`.

`--color-them` SHALL be measurably more saturated than `--color-me` (chroma differential SHALL exceed 0.05 in light theme) so users can scan dialogue ownership at a glance.

#### Scenario: Counterparty chunk carries all four visual cues

- **GIVEN** a transcript chunk with `speaker = "counterparty"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the chunk wrapper SHALL have:
  - `border-left-width: 3px` AND `border-left-color` resolving to `--color-them` AND
  - `background-color` resolving to a non-transparent mix of `--color-them-soft` AND
  - a `[data-testid="speaker-dot"]` element with background `--color-them` rendered before the name AND
  - the speaker name element with `font-weight: 600` and colour `--color-them`

#### Scenario: Me chunk uses the lighter, less saturated variant

- **GIVEN** a transcript chunk with `speaker = "me"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the same four cues SHALL apply but using `--color-me` (lighter, lower chroma) AND `--color-me-soft` (lighter background); the visual hierarchy SHALL clearly place 對方 as the focal point

### Requirement: Animation library usage SHALL follow the framer-motion / magicui / animate-ui split

The web app SHALL declare three animation libraries with disjoint responsibilities:

- `framer-motion` SHALL be used for React component-level entry / exit animations: Pane stagger entry, Tabs cross-fade, modal scale + fade, hover micro-interactions on Buttons and Cards.
- `magicui` SHALL be used for self-contained visual effects: shimmer skeleton, NumberTicker on stat cards, optional Particles on auth shells, Marquee on the calendar import list.
- `animate-ui` SHALL be used for route-level transitions: route change opacity overlay, layout transition when the workspace switches between three-column and stacked.

When two libraries provide the same primitive (e.g. both offer a fade animation), `framer-motion` SHALL win. Animation presets SHALL be centralised in `packages/web/src/lib/motion-presets.ts` exporting typed `Variants` and `Transition` objects (paneEnter, paneStagger, tabContent, modalScale, cardHover).

All animations SHALL be disabled when `window.matchMedia('(prefers-reduced-motion: reduce)').matches` returns true; this SHALL be enforced via a shared `useReducedMotion()` hook applied at the preset level (`framer-motion` already supports this hook natively).

#### Scenario: Reduced motion disables all framer-motion animations

- **GIVEN** the user has `prefers-reduced-motion: reduce` set at the OS level
- **WHEN** any animated component (e.g. a Pane entering with `paneEnter` variants) renders
- **THEN** the component SHALL render at its final state immediately with no transition (no opacity fade, no translateY)

#### Scenario: Motion presets are reused across components

- **GIVEN** the codebase after this change ships
- **WHEN** the source is scanned for inline `framer-motion` `Variants` definitions
- **THEN** preset objects (paneEnter, paneStagger, tabContent, modalScale, cardHover) SHALL all be imported from `packages/web/src/lib/motion-presets.ts`; no component SHALL declare an equivalent inline preset
