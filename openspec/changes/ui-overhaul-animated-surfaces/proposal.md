## Why

P1 (`ui-overhaul-aura-tokens`) shipped the Aura token catalogue and P2
(`ui-overhaul-primitive-upgrade`) shipped the base primitive upgrade
(Dialog, Popover, Tooltip, Toast×4, Progress, Theme toggler, Calendar
picker). What remains is the **effect layer** — the visual / motion
value-adds that turn the static Aura surface into the cyber-violet
editor-feel described in DESIGN.md §1: animated backgrounds, motion-rich
transcript surfaces, a state-aware bar visualizer for in-meeting capture,
and a small family of ported hover / input / success micro-interactions.

This change ships every effect-layer component called out in DESIGN.md
§4 without re-touching the underlying primitives or tokens. It is sized
to land as a single PR-sized slice and is the third of four Spectra
changes (P3 of 4) feeding the Aura overhaul roadmap.

## What Changes

Effect-layer components — no primitive or token changes.

**A. Layout / global level**

- Add an animated **stars background** (animate-ui `backgrounds/stars`)
  to every protected route's shell, **dark mode only**. Gated by
  `prefers-reduced-motion` and the resolved theme; light mode renders
  no stars layer. Mounted inside `<ProtectedShell>` behind the existing
  `main` so it sits below all content.
- Add a **glass dock** primitive (ported from vengenceui `glass-dock`)
  as a reusable component. Initial wiring decision is captured in
  `design.md` — candidate placements: (1) wrap the existing
  `MeetingAudioMiniPlayer` so the player chrome reads as a glass dock,
  (2) host an in-meeting floating control cluster (end / pause / mute),
  (3) be wired later for a focus-mode navigation surface. Sean picks one
  in design review; this change ships the component + ONE initial wiring,
  remaining placements deferred.

**B. Transcript surface**

- Replace the plain `<ol>` rendering inside `transcript-pane.tsx` with
  the magicui `animated-list` pattern so chunks fade-in / lift-in from
  bottom as they stream. Existing `data-testid="transcript-chunk"` +
  per-chunk speaker contract preserved.
- Evaluate the elevenlabs `transcript-viewer` for direct adoption. If
  the package is installable under a permissive license, adopt it as a
  composite component wrapping our chunk rows. If not, extract the
  layout pattern (chunk index, timestamp gutter, hover spotlight, jump
  affordance) into local React + Aura tokens. Decision recorded in
  `design.md`.

**C. In-meeting surface**

- Replace `capture-indicator.tsx`'s random-amplitude sparkline with the
  elevenlabs `bar-visualizer` pattern, ported to React + Aura tokens.
  Renders one of three discrete states per stream:
  - `Connecting` (loading ASR model) → warning orange bars
  - `Listening` (no signal) → `me` / `them` tinted bars, flat baseline
  - `Speaking` (signal detected) → `me` / `them` tinted bars, pulsing
  The new visualizer keeps the existing per-stream rendering contract
  (`data-testid="capture-indicator"` per stream, `data-state` attribute)
  so the meeting-session spec scenarios stay green. Three new i18n keys
  (`meetings.session.barVisualizer.{connecting|listening|speaking}`) land
  in both `zh-TW.json` and `en.json`.

**D. Hover / interaction effect ports**

- Port uiverse `Tiagoadag/cuddly-catfish-6` into a reusable
  `<HoverGlowCard>` composition built from Tailwind utility classes +
  Aura tokens; applied to `meeting-card.tsx` and reserved for future
  recording cards + settings tiles.
- Port uiverse `adamgiebl/pink-chicken-70` button hover motion (motion
  only — colors stay Aura purple) into a new `<PrimaryCtaButton>`
  variant or a className composition consumed by primary CTA buttons.
- Port uiverse `Lakshay-art/curvy-earwig-22` text input motion (label
  float + gradient underline) into the existing `<Input>` as an opt-in
  `variant="curvy"` so it can roll out incrementally without forcing
  every form into the new style.
- Adopt `ui.devsloka.in` success-result micro-interaction as a
  `<SuccessResult>` overlay component. First wiring: staged-attachment
  upload completion + meeting export completion + settings save
  confirmation.
- Port uiverse `Smit-Prajapati/spicy-rat-83` into a reusable motion
  affordance. Sean did not specify a placement — `design.md` proposes
  two candidate landing spots (recording state indicator OR playbook
  generation completion reveal) and the apply phase wires exactly ONE.

**Capability impact**

- `ui-design-system` — gains new ADDED requirements for the effect-layer
  component family (stars background, animated list, bar visualizer,
  glass dock, hover glow card, primary CTA hover, curvy input variant,
  success result overlay, spicy reveal) plus a cross-cutting
  `prefers-reduced-motion` rule and a CaptureIndicator three-state
  display contract.
- `meeting-session` — no requirement-level change. The backend message
  contract (`stream_status`, `silence_warning`, `transcript_chunk`) is
  unchanged; the CaptureIndicator rewrite consumes the same payloads.
  The CaptureIndicator display contract lives in `ui-design-system`.

## Non-Goals

Captured in `design.md` (Goals / Non-Goals section).

## Capabilities

### New Capabilities

None — this change reuses existing capability surfaces.

### Modified Capabilities

- `ui-design-system`: ADDED requirements for the effect-layer component
  family (stars background, animated list, bar visualizer with three
  discrete states for the in-meeting capture indicator, glass dock,
  hover glow card, primary CTA hover, curvy input variant, success
  result overlay, spicy reveal) and a cross-cutting reduced-motion
  rule. All components consume Aura tokens via CSS variables only — no
  raw hex in component className strings.

## Impact

**Code touched**

- `packages/web/src/components/protected-shell.tsx` — mount stars layer
  (dark + motion-allowed only)
- `packages/web/src/components/transcript-pane.tsx` — swap `<ol>` for
  animated list, optionally adopt elevenlabs `transcript-viewer`
- `packages/web/src/components/capture-indicator.tsx` — rewrite to
  three-state bar visualizer
- `packages/web/src/components/meeting-card.tsx` — adopt
  `<HoverGlowCard>` composition
- `packages/web/src/components/ui/button.tsx` (or new variant file) —
  primary CTA hover motion
- `packages/web/src/components/ui/input.tsx` — opt-in `variant="curvy"`
- `packages/web/src/components/meeting-audio-mini-player.tsx` (if glass
  dock wiring lands there) — wrap chrome
- New: `packages/web/src/components/animate-ui/backgrounds/stars.tsx`,
  `packages/web/src/components/magicui/animated-list.tsx`,
  `packages/web/src/components/ui/glass-dock.tsx`,
  `packages/web/src/components/ui/hover-glow-card.tsx`,
  `packages/web/src/components/ui/success-result.tsx`,
  `packages/web/src/components/ui/bar-visualizer.tsx`,
  `packages/web/src/components/ui/spicy-reveal.tsx`

**Locales (i18n parity)**

- `packages/web/src/locales/zh-TW.json` + `packages/web/src/locales/en.json`
  gain `meetings.session.barVisualizer.connecting`,
  `meetings.session.barVisualizer.listening`,
  `meetings.session.barVisualizer.speaking`. Any string emitted by
  the new components MUST land in both files; the `locales.test.ts`
  deep-equal test catches drift.

**Dependencies**

- May add `motion` / `framer-motion` peer if not already present
  (already used in transcript-pane). No new heavy dependencies expected.
- elevenlabs `transcript-viewer` adoption is conditional on a license /
  install spike (see design.md Risk section).

**Out of scope (hard)**

- No token / `index.css` edits (P1 territory)
- No base primitive edits — Dialog, Popover, Tooltip, Toast, Progress,
  Theme toggler, Calendar (P2 territory)
- No routing changes (P4 territory)
- No meeting detail page layout restructure (P5 territory)
- No backend / Python / Alembic / WebSocket message changes
- No edits to single-channel-recording-entry (S27) files

**DB**

- No schema changes. The speaker label `'them'` is and remains banned.

**Risk**

- Motion side-effects in CI / happy-dom: every animated component MUST
  short-circuit when `prefers-reduced-motion: reduce` to keep tests
  deterministic.
- uiverse ports are CSS snippets — each port is its own task and must
  produce React + Tailwind + Aura tokens (no raw hex).
- elevenlabs / vengenceui source-availability spike must complete
  before adoption tasks unlock.

