---
name: Aura (Meeting Playbook)
description: Aura-anchored design system for Meeting Playbook. Dark-first, light derived from Aura *-soft variants. All tokens consumed via oklch() CSS variables — no raw hex in component class strings.
authors:
  - Sean Chen
modes:
  - dark
  - light
defaultMode: dark
fonts:
  sans: "Inter, Noto Sans TC, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
  mono: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"

colors:
  dark:
    background: "#15141B"
    surface: "#1F1D26"
    surface-2: "#2A2832"
    surface-3: "#363441"
    foreground: "#EDECEE"
    muted-foreground: "#B8B6BC"
    subtle-foreground: "#8A8890"
    border: "#3D3B45"
    border-strong: "#4F4D58"
    primary: "#A277FF"
    primary-hover: "#B392FF"
    primary-soft: "#3D375E"
    primary-foreground: "#15141B"
    secondary: "#61FFCA"
    secondary-foreground: "#15141B"
    accent: "#F694FF"
    accent-foreground: "#15141B"
    success: "#61FFCA"
    success-soft: "#2C4A3D"
    warning: "#FFCA85"
    warning-soft: "#4A3E2A"
    danger: "#FF6767"
    danger-soft: "#4A2A2A"
    info: "#82E2FF"
    info-soft: "#2A3D4A"
    me: "#82E2FF"
    them: "#F694FF"
    muted: "#6D6D6D"
    recording: "#FF6767"

  light:
    background: "#EDECEE"
    surface: "#FFFFFF"
    surface-2: "#E0DEE2"
    surface-3: "#D2D0D6"
    foreground: "#15141B"
    muted-foreground: "#5C5A62"
    subtle-foreground: "#8A8890"
    border: "#C7C5CB"
    border-strong: "#A8A6AE"
    primary: "#8464C6"
    primary-hover: "#7355B5"
    primary-soft: "#E8E0F5"
    primary-foreground: "#FFFFFF"
    secondary: "#54C59F"
    secondary-foreground: "#15141B"
    accent: "#C17AC8"
    accent-foreground: "#FFFFFF"
    success: "#54C59F"
    success-soft: "#DDF5EA"
    warning: "#C7A06F"
    warning-soft: "#F5ECDD"
    danger: "#C55858"
    danger-soft: "#F5DDDD"
    info: "#6CB2C7"
    info-soft: "#DDEDF2"
    me: "#6CB2C7"
    them: "#C17AC8"
    muted: "#6D6D6D"
    recording: "#C55858"

rounded:
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
  pill: 999px

spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 24px
  6: 32px
  7: 48px

typography:
  display:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: 600
    letterSpacing: -0.02em
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 600
    letterSpacing: -0.015em
  h2:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: 600
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 600
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  small:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 400
  code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: 400

shadow:
  dark:
    sm: "none"
    md: "0 1px 0 rgba(0,0,0,0.3) inset"
    lg: "0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.4)"
  light:
    sm: "0 1px 2px rgba(20,14,40,0.04)"
    md: "0 4px 16px rgba(20,14,40,0.06), 0 1px 3px rgba(20,14,40,0.04)"
    lg: "0 12px 32px rgba(20,14,40,0.1), 0 2px 6px rgba(20,14,40,0.06)"
---

## 1. Visual Theme & Atmosphere

**Cyber-violet editor-feel.** The anchor is [Aura by Dalton Menezes](https://github.com/daltonmenezes/aura-theme) — a theme born in code editors and terminal emulators where deep violet backgrounds carry punchy magenta + cyan accents. Translated to a product UI, this becomes:

- **Dark mode is the canon.** Backgrounds are deep enough to feel ink-on-vellum but never pure black (`#15141B` carries a faint purple cast at ~17% lightness). Foreground (`#EDECEE`) is near-white with the same purple tint — never sterile.
- **Light mode is the mirror.** Same hue family, inverted lightness. Accent colors swap to Aura's `*-soft` variants so they don't blow out a white-ish background.
- **Color is communicative, not decorative.** Purple = identity / primary action. Cyan-green = success / health. Orange = warning / pause. Red = error / recording. Blue = me (the speaker). Pink = them (the counterparty). These role bindings are **invariant** across both modes.
- **Density is editor-like.** Tight type scale, 8pt grid, sharp 4/6/8px radii. The UI should feel like a serious instrument, not a marketing site.
- **No emoji anywhere.** Iconography comes from `animate-ui/icons/`, `lucide-react`, or `magicui` motion components.

## 2. Color Palette & Roles

### Dark mode (primary)

- **Ink Violet (`#15141B`)** — Primary background. Deep, slightly purple. Feels heavier than `#000` but reads identically as "dark."
- **Surface Slate (`#1F1D26`)** — Cards, popovers, sidebars. One step up from background, no shadow needed.
- **Surface Lift (`#2A2832`)** — Hover states, inset panels, secondary cards.
- **Foreground Bone (`#EDECEE`)** — Primary text. Soft, never pure white.
- **Muted Fog (`#B8B6BC`)** — Secondary text, labels, captions.
- **Subtle Smoke (`#8A8890`)** — Disabled text, placeholder, divider labels.
- **Hairline (`#3D3B45`)** — Default borders. Just visible enough to separate.
- **Hairline Bold (`#4F4D58`)** — Strong borders (focused inputs, table headers).
- **Aura Purple (`#A277FF`)** — Primary action. Buttons, active tabs, focus rings, links.
- **Aura Purple Hover (`#B392FF`)** — Hover state for purple buttons. One step lighter.
- **Aura Purple Soft (`#3D375E`)** — Tinted primary backgrounds (selected rows, subtle highlights).
- **Cyber Green (`#61FFCA`)** — Success, completion, "live" indicators.
- **Sunset Orange (`#FFCA85`)** — Warning, in-progress, gentle attention.
- **Vermillion (`#FF6767`)** — Danger, error, recording dot.
- **Glacier Blue (`#82E2FF`)** — Info messages **and** the **me** speaker tint.
- **Magenta Bloom (`#F694FF`)** — Accent **and** the **them** (counterparty) speaker tint.
- **Mist (`#6D6D6D`)** — Truly muted text (timestamps, metadata side notes).

### Light mode (mirror)

- **Mist Bone (`#EDECEE`)** — Primary background. Slightly purple-tinted off-white.
- **Pure Surface (`#FFFFFF`)** — Cards, popovers (true white to lift off mist bone).
- **Aura Violet Soft (`#8464C6`)** — Primary action (softer than dark mode's `#A277FF` so it doesn't vibrate on white).
- **Mint Soft (`#54C59F`)** — Success.
- **Sand Soft (`#C7A06F`)** — Warning.
- **Rust Soft (`#C55858`)** — Danger.
- **Steel Blue (`#6CB2C7`)** — Info / me speaker.
- **Mauve Soft (`#C17AC8`)** — Accent / them speaker.

### Speaker color rule

`--color-me` and `--color-them` are **tint colors used for chunk backgrounds, badges, and avatar borders** — they are NOT foreground text colors. Transcript chunk text always uses `--color-foreground` against a `me-soft` or `them-soft` background to maintain WCAG AA contrast.

### WCAG contrast notes

- Dark fg on dark bg: ~11.5:1 ✓ AAA
- Light fg on light bg: ~11.2:1 ✓ AAA
- Primary purple text on dark bg: ~5.8:1 ✓ AA
- Primary purple text on light bg: ~4.8:1 ✓ AA
- `me` and `them` as foreground text on default bg: **not sufficient** — use only as backgrounds/tints with primary foreground text on top.

## 3. Typography Rules

- **Sans-serif: Inter (Latin) + Noto Sans TC (Traditional Chinese).** Bilingual UI; Inter handles diacritics and CJK fallback chain pushes Noto Sans TC up when Chinese codepoints appear.
- **Monospace: JetBrains Mono.** For code blocks, transcript timestamps, file paths.
- **Weight discipline:** 400 body, 500 emphasis, 600 headings. No 700+ unless display-only.
- **Letter-spacing:** Tight at large sizes (-0.01 to -0.02em on headings), default at body.
- **Density:** Default scale is "cozy." Density variants (`compact` / `comfortable`) ride on top via `[data-density]` selectors. Type scale collapses or expands proportionally.
- **Line-height:** 1.5 for body, 1.2 for headings, 1.7 for prose blocks (markdown content).

## 4. Component Stylings

- **Buttons:** Sharp 4px radius. Primary = solid purple fill with bone foreground; Secondary = transparent with hairline-bold border; Ghost = transparent, foreground text only. Hover lifts by 1 level (primary → primary-hover, ghost → surface-2 bg). Cursor pointer on enabled, not-allowed on disabled. Focus ring is 2px outline using `--color-primary` at 25% opacity.
- **Cards / Containers:** 6-8px radius. `surface` background. **No drop shadow in dark mode** — separation comes from background-vs-surface lightness step. Light mode keeps soft shadows (`shadow-md`).
- **Inputs / Textareas:** 4px radius. `surface` background. Border `border` color at rest, `primary` at focus. Placeholder uses `subtle-foreground`. Custom port of [uiverse Lakshay-art curvy-earwig-22](https://uiverse.io/Lakshay-art/curvy-earwig-22) with our tokens — animated label float, gradient underline on focus.
- **Dialogs:** 8px radius. Backdrop blur (8px) + `background` at 80% opacity. Uses [animate-ui/base/dialog](https://animate-ui.com/docs/components/base/dialog) for entry/exit motion.
- **Popovers:** 6px radius. [animate-ui/base/popover](https://animate-ui.com/docs/components/base/popover) — used for transcript chunk action menus.
- **Tooltips:** 4px radius. [animate-ui/primitives/animate/tooltip](https://animate-ui.com/docs/primitives/animate/tooltip). Background uses `foreground` color, text uses `background` color (inverse). Mounted everywhere a hover would reveal supplementary info.
- **Progress:**
  - **Determinate** — [animate-ui/base/progress](https://animate-ui.com/docs/components/base/progress).
  - **Indeterminate** (loading without known total) — ported [uiverse gustavofusco rare-pug-90](https://uiverse.io/gustavofusco/rare-pug-90) animation, recolored to our purple.
- **Toast:** 4 variants:
  - `info` — Glacier Blue accent stripe
  - `success` — Cyber Green accent stripe
  - `warning` — Sunset Orange accent stripe
  - `error` — Vermillion accent stripe
- **Theme toggler:** Replaces the current dropdown with [magicui animated-theme-toggler](https://magicui.design/docs/components/animated-theme-toggler) — circular reveal animation between dark/light.
- **Calendar picker:** [shadcnblocks calendar-standard-3](https://www.shadcnblocks.com/component/calendar/calendar-standard-3) for date selection in meeting create/edit.
- **Card hover:** Port of [uiverse Tiagoadag/cuddly-catfish-6](https://uiverse.io/Tiagoadag/cuddly-catfish-6) — subtle lift + border glow on hover. Used on meeting cards, recording cards, settings tiles.
- **Button hover (special):** Port of [uiverse adamgiebl/pink-chicken-70](https://uiverse.io/adamgiebl/pink-chicken-70) for primary CTA buttons. Animation pattern only — colors recolored to our purple/foreground.
- **Animated list (transcript chunks):** [magicui animated-list](https://magicui.design/docs/components/animated-list) — chunks fade-in from bottom as they stream.
- **Bar visualizer (in-meeting capture):** [elevenlabs bar-visualizer](https://ui.elevenlabs.io/docs/components/bar-visualizer) — states: `Connecting` (loading model), `Listening` (default), `Speaking` (audio detected). Color shifts: `Listening` = `me` blue, `Speaking` = `me` blue pulsing, `Connecting` = warning orange.
- **Transcript viewer (combo):** [elevenlabs transcript-viewer](https://ui.elevenlabs.io/docs/components/transcript-viewer) — evaluate whether to adopt directly or extract pattern. If adopted, replaces TranscriptPane's list rendering.
- **Success result:** [ui.devsloka.in success-result](https://ui.devsloka.in/components/success-result) — for completion states after upload, export, save.
- **Glass dock:** [vengenceui glass-dock](https://www.vengenceui.com/docs/glass-dock) — placement TBD (candidate: mini player wrapper, or floating navigation when in focus mode).
- **Stars background:** [animate-ui backgrounds/stars](https://animate-ui.com/docs/components/backgrounds/stars) — dark mode only, subtle layer on body background. Disabled in `prefers-reduced-motion`.

## 5. Layout Principles

- **8pt grid.** All spacing is a multiple of 4 (`--space-1` = 4px); component-level breathing room is 8/16/24/32.
- **Pane / Workspace primitives stay.** `<Pane>` composes inside `<Workspace>` — meeting detail will eventually decompose into phase-aware sub-views (Pre / In / Post), but the primitives are unchanged.
- **Density toggles.** `[data-density="compact"]` and `[data-density="comfortable"]` provide ±15% adjustment to type+spacing scale.
- **No raw hex in component code.** Every color reference uses a CSS variable. Tailwind's arbitrary-value syntax (`text-(--color-primary)`) is allowed.
- **Motion is purposeful.** Animations exist to communicate state change (entry, focus, completion). Decorative motion (stars, hover scale) respects `prefers-reduced-motion`.

## 6. Roadmap

This DESIGN.md is consumed by 4 Spectra changes, each one PR-sized:

| Phase | Change | Scope |
|---|---|---|
| P1 | `ui-overhaul-aura-tokens` | Section 2 tokens, Section 3 typography, base radii/shadows. No new components. |
| P2 | `ui-overhaul-primitive-upgrade` | Section 4 base primitives: Dialog, Popover, Tooltip, Toast (×4), Progress, Loading, Theme toggler, Calendar picker. |
| P3 | `ui-overhaul-animated-surfaces` | Section 4 effect-layer components: Stars bg, Animated list, Bar visualizer, Transcript viewer, Card hover, Button hover, Input style, Success result, Glass dock. |
| P4 | `ui-overhaul-ia-refactor` | Routing changes (砍 `/calendar/upcoming`, 新增 `/recordings`). Settings stays flat at 7 items per `並列就好` decision. |
| P5 | `ui-overhaul-meeting-detail-phase-aware` | Deferred — meeting detail page restructure into Pre/In/Post phase-aware sub-views. Discuss separately. |

Each phase ships independently. P1 must merge before P2/P3/P4. P5 deferred until P1-P4 land.
