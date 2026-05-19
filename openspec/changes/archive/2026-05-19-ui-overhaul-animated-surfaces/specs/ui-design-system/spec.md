# ui-design-system Specification Delta — ui-overhaul-animated-surfaces

## ADDED Requirements

### Requirement: All effect-layer motion SHALL honor prefers-reduced-motion

Every component introduced by this change that schedules a CSS animation, a framer-motion transition, a `requestAnimationFrame` loop, or any `setInterval`-driven visual update SHALL gate that motion behind a `prefers-reduced-motion` check. When `window.matchMedia('(prefers-reduced-motion: reduce)').matches` is true, the component SHALL render its final visual state without animation. The check SHALL be implemented via a shared hook in `packages/web/src/hooks/` (one canonical implementation) and SHALL react to runtime media-query changes so a mid-session preference change is honored.

#### Scenario: Reduced-motion user sees no animation on protected route entry

- **GIVEN** a logged-in user with OS-level `prefers-reduced-motion: reduce` enabled
- **WHEN** the user navigates to any protected route
- **THEN** the stars background SHALL render `null`, transcript chunks SHALL appear at their final position without fade-in, and the bar visualizer bars SHALL render their target height without per-frame interpolation

#### Scenario: Mid-session preference flip stops in-flight animations

- **GIVEN** an active meeting page where the user toggles `prefers-reduced-motion: reduce` ON at runtime
- **WHEN** the next render commits after the media-query change event fires
- **THEN** any in-flight animations SHALL settle to their final frame within the same animation frame and SHALL NOT continue interpolating

### Requirement: Effect-layer components SHALL consume Aura tokens via CSS variables only

Every component file shipped by this change (`stars.tsx`, `animated-list.tsx`, `bar-visualizer.tsx`, `glass-dock.tsx`, `hover-glow-card.tsx`, `success-result.tsx`, `spicy-reveal.tsx`, the curvy input variant, and the primary CTA hover variant) SHALL express color through `--color-*` CSS custom properties (e.g., `bg-(--color-primary)`, `text-(--color-foreground)`, `border-(--color-border)`). Raw hex literals (`#a277ff`), `rgb(...)` / `rgba(...)` function calls, and arbitrary color values inside Tailwind className strings are design-system violations and SHALL NOT appear in these files. Inline `style` props expressing colors SHALL reference `var(--color-*)` rather than literal hex.

#### Scenario: No raw color literals in effect-layer files

- **GIVEN** the effect-layer component files shipped by this change
- **WHEN** a reviewer greps each file for `#[0-9a-fA-F]{3,8}` (excluding source-map comments) and for `rgb(` / `rgba(` outside `index.css`
- **THEN** zero matches SHALL be returned

### Requirement: Stars background SHALL mount only on protected routes in dark mode

The animated stars background SHALL render inside `<ProtectedShell>` behind the `<main>` element so that page content paints on top. The component SHALL evaluate three gates on every theme or media-query change:

1. The resolved theme is `dark`.
2. `prefers-reduced-motion: reduce` is NOT matched.
3. The current route is a protected (authenticated) route.

If any gate fails, the component SHALL render `null`. The component SHALL NOT mount on public routes (login, signup, error pages). The star count SHALL be bounded (≤ 60) so the per-frame paint cost stays modest on low-end devices.

#### Scenario: Light-mode protected route hides stars

- **GIVEN** a user on a protected route with the theme set to light
- **WHEN** the protected shell renders
- **THEN** the `<Stars />` component SHALL return `null` and no canvas / SVG layer for stars SHALL be present in the DOM

#### Scenario: Public route never mounts stars

- **GIVEN** an unauthenticated user on the `/login` route in dark mode
- **WHEN** the login page renders
- **THEN** no stars background SHALL be present in the DOM

### Requirement: CaptureIndicator SHALL render one of four discrete states per stream

The in-meeting `<CaptureIndicator>` component SHALL render one bar visualizer row per capture stream (`me`, `counterparty`). Each row SHALL expose `data-testid="capture-indicator"`, `data-stream="me"|"counterparty"`, and `data-state` set to exactly one of `"connecting"`, `"listening"`, `"speaking"`, or `"off"`.

Display contract per state:

- **`connecting`** — bars use the `--color-warning` token; motion is a slow pulse (≥ 1.0s cycle).
- **`listening`** — bars use the stream's speaker tint (`--color-me` for the me row, `--color-them` for the counterparty row); bar amplitudes hold a low flat baseline.
- **`speaking`** — bars use the same speaker tint as `listening`; amplitudes pulse with a faster cycle (≤ 400ms) to communicate active signal.
- **`off`** — bars render the muted baseline using `--color-border`; no animation.

State derivation from the existing WebSocket payloads SHALL follow this mapping:

- `streamStatus[s] === "stopped"` OR `ending === true` → `off`.
- `streamStatus[s] === "active"` AND no `transcript_chunk` for stream `s` has been received within the first 8 seconds since the stream became active → `connecting`.
- `streamStatus[s] === "active"` AND a `transcript_chunk` for stream `s` arrived within the last ~2 seconds → `speaking`.
- `streamStatus[s] === "active"` otherwise → `listening`.
- `streamStatus[s] === "silence"` → `listening`.

The component SHALL NOT require backend message contract changes. Three i18n keys SHALL exist in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`: `meetings.session.barVisualizer.connecting`, `meetings.session.barVisualizer.listening`, `meetings.session.barVisualizer.speaking`. Each key SHALL be rendered as the visible label or accessible name for its corresponding state.

#### Scenario: Newly-active stream with no chunks yet renders connecting

- **GIVEN** a meeting that has just transitioned to `in_progress`
- **WHEN** `streamStatus = {me: "active", counterparty: "active"}` and no `transcript_chunk` has arrived for either stream within the first 8 seconds
- **THEN** both rows SHALL render with `data-state="connecting"` and the visible label SHALL resolve from `meetings.session.barVisualizer.connecting`

#### Scenario: Active stream with recent chunk renders speaking

- **GIVEN** a stream's `streamStatus[s] === "active"`
- **WHEN** a `transcript_chunk` for stream `s` was received within the last 2 seconds
- **THEN** the row for stream `s` SHALL render `data-state="speaking"`, the bar tint SHALL resolve to the stream's speaker color token (`--color-me` for me, `--color-them` for counterparty), and bar amplitudes SHALL pulse

#### Scenario: Stopped stream renders off

- **GIVEN** a stream's `streamStatus[s] === "stopped"`
- **WHEN** the component renders
- **THEN** the row for stream `s` SHALL render `data-state="off"` with bars at the muted baseline using `--color-border` and no animation

##### Example: state derivation table

| streamStatus[s] | seconds since stream active | last chunk age | ending | expected data-state |
|-----------------|-----------------------------|----------------|--------|---------------------|
| `active`        | 3                           | none yet       | false  | `connecting`        |
| `active`        | 12                          | none yet       | false  | `listening`         |
| `active`        | 30                          | 0.5s           | false  | `speaking`          |
| `active`        | 30                          | 5s             | false  | `listening`         |
| `silence`       | 30                          | n/a            | false  | `listening`         |
| `stopped`       | 30                          | n/a            | false  | `off`               |
| `active`        | 30                          | 0.5s           | true   | `off`               |

### Requirement: Transcript chunks SHALL fade-in on mount via the animated-list pattern

The `<TranscriptPane>` chunk list SHALL render new chunks with a fade-in + lift-in entry animation derived from the magicui `animated-list` pattern. The animation SHALL be implemented via framer-motion variants on the existing `<TranscriptChunkRow>`, NOT via a global CSS rule. The animation SHALL be skipped under `prefers-reduced-motion: reduce`. The existing chunk DOM contract — `data-testid="transcript-chunk"`, `data-speaker`, the per-chunk action menu, and speaker tinting — SHALL be preserved exactly.

#### Scenario: New chunk mounts with fade-in

- **GIVEN** a user watching a transcript stream in dark mode with motion allowed
- **WHEN** a new `transcript_chunk` is appended to the chunk list
- **THEN** the new chunk DOM element SHALL transition `opacity: 0 → 1` and translate from a small positive Y offset to its final position within a single animation, and the previous chunks SHALL NOT re-animate

#### Scenario: Reduced-motion user sees chunks at final position immediately

- **GIVEN** a user with `prefers-reduced-motion: reduce`
- **WHEN** new chunks are appended
- **THEN** chunks SHALL render at their final position with no opacity transition

### Requirement: Glass dock SHALL be a reusable container with one initial wiring

A `<GlassDock>` component SHALL be introduced under `packages/web/src/components/ui/` as a generic container exposing `children` and an optional `className`. Visual contract: backdrop-blur, inner border highlight, rounded corners (token `--radius-lg`), and a subtle ambient shadow consuming `--shadow-lg` (dark) or the equivalent light-mode token. The component SHALL NOT position itself; callers position it via `className`.

This change SHALL wire `<GlassDock>` to exactly one existing surface (the meeting audio mini-player chrome). Additional placements (in-meeting floating control cluster, focus-mode navigation) SHALL be deferred to a future change.

#### Scenario: Mini-player chrome reads as a glass dock

- **GIVEN** a user with an open meeting and the audio mini-player visible
- **WHEN** the mini-player renders
- **THEN** its outer container SHALL be a `<GlassDock>` instance and SHALL apply backdrop-blur with the token-driven border, radius, and shadow

### Requirement: Card hover glow SHALL be a reusable composition consumed by meeting cards

A `<HoverGlowCard>` composition (or an equivalent className composition exposed from a shared module) SHALL apply the ported uiverse `cuddly-catfish-6` hover effect — subtle lift plus border glow — using only Aura color tokens. `MeetingCard` SHALL adopt this composition on the meeting list and Kanban surfaces. The composition SHALL be authored so future surfaces (recording cards, settings tiles) can adopt it without further code change.

#### Scenario: Meeting card hover triggers lift and border glow

- **GIVEN** the meetings list rendered in either Kanban or List view in motion-allowed mode
- **WHEN** the user hovers a meeting card
- **THEN** the card SHALL translate upward by a small amount, the border color SHALL transition to a primary-tinted variant, and no className SHALL reference a raw hex literal

#### Scenario: Reduced-motion user sees no lift transition

- **GIVEN** a user with `prefers-reduced-motion: reduce`
- **WHEN** the user hovers a meeting card
- **THEN** the card SHALL NOT translate; the border color change SHALL apply instantly without a transition

### Requirement: Primary CTA buttons SHALL expose the ported hover motion variant

Primary CTA buttons SHALL adopt the ported `pink-chicken-70` hover motion (motion pattern only — colors stay Aura purple). Adoption SHALL be either (a) a new `data-cta="primary"` selector on the existing `<Button>` component or (b) a new `<PrimaryCtaButton>` wrapper — both forms are acceptable as long as the hover motion engages on enabled primary CTAs and is suppressed on disabled buttons. Color tokens SHALL remain `--color-primary` / `--color-primary-hover` / `--color-primary-foreground`.

#### Scenario: Disabled primary CTA suppresses hover motion

- **GIVEN** a primary CTA rendered in the disabled state
- **WHEN** the user hovers the button
- **THEN** the hover motion SHALL NOT engage and the button SHALL retain its disabled styling

### Requirement: Inputs SHALL expose a curvy variant for opt-in adoption

The shared `<Input>` component SHALL gain a `variant` prop with values `"default" | "curvy"`. The `"default"` variant SHALL preserve the existing rendering and behavior exactly. The `"curvy"` variant SHALL apply the ported `curvy-earwig-22` motion — floating label and gradient underline on focus — using Aura tokens. This change SHALL NOT roll the curvy variant across every form; only the variant itself ships here.

#### Scenario: Default variant unchanged

- **GIVEN** any consumer rendering `<Input />` (or `<Input variant="default" />`)
- **WHEN** the input renders
- **THEN** the DOM and behavior SHALL be identical to the pre-change baseline

#### Scenario: Curvy variant floats label on focus

- **GIVEN** an `<Input variant="curvy" />` with motion allowed
- **WHEN** the input gains focus
- **THEN** the label SHALL translate upward and shrink, and a token-driven gradient underline SHALL appear; under reduced motion the same final state SHALL appear without the transition

### Requirement: Success result overlay SHALL ship as a reusable micro-interaction

A `<SuccessResult>` component SHALL render a short-lived success micro-interaction modeled on `ui.devsloka.in`'s success-result pattern. Props: `message: string` and `onAnimationComplete?: () => void`. Color tokens consumed: `--color-success` for the check glyph, `--color-foreground` for the message, `--color-success-soft` for any tinted backdrop. The animation SHALL run once per mount and SHALL be skipped under reduced motion (the final "check" frame appears immediately and `onAnimationComplete` fires on the next tick).

#### Scenario: First wiring fires on attachment upload completion

- **GIVEN** the staged-attachment dropzone has completed an upload
- **WHEN** the success transition is dispatched
- **THEN** a `<SuccessResult>` SHALL render with a token-driven check glyph and the localized success message; under reduced motion the check SHALL appear immediately

### Requirement: Spicy reveal SHALL ship as a one-shot, persisted reveal animation

A `<SpicyReveal>` component SHALL wrap content and play the ported `spicy-rat-83` reveal animation exactly once per `revealKey`. The component SHALL persist the seen state in `localStorage` under the key `playbookRevealSeen:<revealKey>` (or an equivalent scoped key) so re-visits SHALL NOT replay the animation. Initial wiring SHALL be the post-meeting playbook content area, triggered the first time the user opens a freshly-generated playbook. Under reduced motion the wrapper SHALL render its `children` at the final state without animation.

#### Scenario: Reveal plays once for a freshly-generated playbook

- **GIVEN** a meeting whose playbook has just been generated and never opened
- **WHEN** the user opens the playbook view for the first time in motion-allowed mode
- **THEN** the playbook content area SHALL play the spicy reveal animation once, and `localStorage['playbookRevealSeen:<meetingId>']` SHALL be set to a truthy value

#### Scenario: Reveal does not replay on subsequent visits

- **GIVEN** a meeting whose `playbookRevealSeen:<meetingId>` is already set
- **WHEN** the user re-opens the playbook view
- **THEN** the playbook content area SHALL render immediately at its final state with no animation

### Requirement: Bar visualizer SHALL be a reusable Aura-token component independent of CaptureIndicator

A `<BarVisualizer>` component SHALL be exported from `packages/web/src/components/ui/bar-visualizer.tsx`. Props: `state: "connecting" | "listening" | "speaking" | "off"`, `tone: "me" | "them" | "warning"`, optional `barCount: number` (default 10), and `ariaLabel: string`. Color resolution SHALL map `tone` to `--color-me`, `--color-them`, or `--color-warning`. Motion behavior per state SHALL match the CaptureIndicator display contract. The component SHALL be free of meeting-session domain knowledge so future surfaces (e.g., a voice-enrollment UI) can reuse it.

#### Scenario: ariaLabel exposes accessible name

- **GIVEN** a `<BarVisualizer state="listening" tone="me" ariaLabel="Microphone listening" />`
- **WHEN** the component renders
- **THEN** the root element SHALL expose `aria-label="Microphone listening"` (or `role="img"` + `aria-label`) so assistive technology can announce the visual state

