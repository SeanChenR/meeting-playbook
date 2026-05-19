## Context

DESIGN.md §1 anchors the project on Aura by Dalton Menezes — a
cyber-violet editor theme that, in product form, demands punchy
state-communicating motion on top of a deep, slightly purple surface.
P1 shipped the tokens; P2 shipped the base primitives. What the UI
still feels like is "a static Aura surface" rather than "a serious
instrument" — there is no atmospheric depth, transcript chunks arrive
without any visual cadence, the in-meeting capture indicator emits
random sparkline noise instead of a state-aware signal, and primary
CTAs / cards / inputs share the same flat hover-color-shift as every
slice-7 surface. This change adds the effect layer that DESIGN.md §4
enumerates without re-touching the underlying primitive or token work.

Two implementation realities shape the design:

1. Several listed sources are uiverse CSS snippets. They cannot be
   consumed via `npm install`; each port produces a small React +
   Tailwind component constrained to Aura tokens (no raw hex).
2. Two sources (elevenlabs `transcript-viewer` + `bar-visualizer`,
   vengenceui `glass-dock`) have unknown packaging / license status.
   We treat both as **spike-then-decide**: a half-day install spike
   precedes the adoption task; if not adoptable, we extract the pattern
   into a local component with the same component name + props shape.

The CaptureIndicator rewrite is the only piece that touches a domain
capability spec (`meeting-session`). Everything else fits inside
`ui-design-system` as a new effect-layer requirement block.

## Goals / Non-Goals

**Goals:**

- Ship every effect-layer component listed in DESIGN.md §4 as reusable
  pieces that consume Aura tokens via CSS variables.
- Honor `prefers-reduced-motion: reduce` in every motion path. When set,
  motion components either render their final frame immediately or fall
  back to a static equivalent.
- Replace the random-amplitude `CaptureIndicator` with a three-state
  bar visualizer (`Connecting` / `Listening` / `Speaking`) whose
  state mapping is well-defined and testable without real audio.
- Keep the `transcript-pane` chunk DOM contract (per-chunk `data-testid`,
  speaker tinting, action menu) intact while swapping the list render.
- Ship the glass dock with exactly ONE concrete wiring; defer other
  placement candidates to a future change so the slice stays PR-sized.
- Land any new user-visible string in both `zh-TW.json` and `en.json`
  in the same commit. The deep-equal `locales.test.ts` catches drift.

**Non-Goals:**

- Editing `packages/web/src/index.css` or any color / radius / shadow
  token (owned by P1).
- Editing the base primitives — Dialog, Popover, Tooltip, Toast,
  Progress (determinate / indeterminate), Theme toggler, Calendar —
  owned by P2.
- Routing / IA changes (owned by P4).
- Meeting detail page restructure into Pre / In / Post phase-aware
  sub-views (deferred to P5).
- Backend, Python, Alembic, WebSocket message, or API contract changes.
- Editing any file enumerated by `single-channel-recording-entry` (S27).
- Adopting `'them'` (with apostrophes-as-quotes) as a literal anywhere
  in DB code or schema; `counterparty` remains the only valid speaker
  label on the wire.
- Rolling the `variant="curvy"` input across every form — only the
  variant + opt-in adoption ship here.

## Decisions

### Stars background lives inside the protected shell, dark + motion only

The animate-ui `stars` background mounts inside `<ProtectedShell>` as a
sibling element rendered behind `<main>` (using `position: absolute`
inside a positioned parent or a stacking-context wrapper). Three gates
determine whether stars render:

- The resolved theme is `dark` — read from the existing theme provider.
- `window.matchMedia('(prefers-reduced-motion: reduce)').matches` is
  false.
- The current route is a protected (authenticated) route. Public routes
  (login, signup) do not mount stars.

When any gate fails, the component returns `null`. There is no static
"stars without motion" fallback — DESIGN.md §4 already labels stars as
purely decorative, so a no-render fallback is preferred over a
half-broken still image. A single `useMatchMedia` hook reads
`prefers-reduced-motion` and updates on change.

**Alternative considered:** mount stars at the document root via a
portal. Rejected because gating per-route (e.g., hiding stars during a
hypothetical print view) becomes harder; per-shell mount is the
simpler containment.

### Glass dock ships with exactly one initial wiring; remaining placements deferred

DESIGN.md lists three candidate placements:

1. Wrap `<MeetingAudioMiniPlayer>` so the player chrome reads as a
   floating glass dock.
2. Host an in-meeting floating control cluster (end / pause / mute).
3. Become a focus-mode navigation surface (P5 territory).

This change ships placement (1) — wrap the existing mini-player chrome
— because the mini-player is already a floating, position-fixed
surface, and a glass-dock visual replaces nothing functional. Placement
(2) is deferred: the in-meeting toolbar currently lives inline in
metadata-card and changing its position couples to meeting-session
state. Placement (3) is P5 territory. The `<GlassDock>` component is
authored as a generic container so a future change can wire the other
candidates without reshaping the component.

**Alternative considered:** ship the component with no initial wiring
and treat all three placements as separate follow-ups. Rejected because
shipping a UI component with zero consumers is a code-review smell and
delays the visible value of P3.

### Spicy-rat-83 reveal wires to playbook generation completion

DESIGN.md leaves the spicy-rat-83 placement open. Two candidates were
considered:

- **Candidate A: recording state indicator** — replace the small red
  dot on the metadata-card when `meeting.recording_state === "active"`.
  Rejected because the recording dot is already a deliberate
  low-attention affordance (`recording` capability rules forbid
  distracting motion that could draw the eye during a live meeting).
- **Candidate B: playbook generation completion reveal** — when the
  post-meeting `playbook-generation` pipeline finishes and the user
  first opens the post-meeting playbook view, the playbook content
  area performs a one-shot spicy-rat-83 reveal animation. **Selected.**
  This event is rare, user-initiated, and matches the "unlock"
  semantics the original snippet conveys. The reveal honors
  `prefers-reduced-motion` and falls back to a `motion-safe:opacity-0
  → opacity-100` 200ms fade.

Sean to confirm during design review; if rejected, the alternative
landing spot becomes "first-time meeting export download dialog" and
the rest of the design is unaffected.

### CaptureIndicator becomes a three-state bar visualizer

The existing component drives random amplitudes at a 220ms interval.
That conveys "something is happening" but does not communicate the
distinct meeting-session lifecycle states the user actually needs:

- **`Connecting`** — the ASR provider is loading (model download /
  warm-up). Bars render warning-orange and pulse slowly (1.2s cycle).
  Test asserts `data-state="connecting"`.
- **`Listening`** — capture is live but no audio energy is detected.
  Bars render `me` blue (or `them` pink for the counterparty row) at a
  flat low baseline. Test asserts `data-state="listening"`.
- **`Speaking`** — capture is live and signal is detected. Bars render
  the same speaker tint but with a pulsing animation that increases
  amplitude proportionally to a smoothed energy signal. Test asserts
  `data-state="speaking"`.

The component still accepts `streamStatus` as today (`active` /
`silence` / `stopped`). Mapping:

- ASR provider warm-up phase (new) → `connecting`. This is detected via
  a new (already-emitted by backend) `asr_loading` / `asr_ready`
  message OR via a local "no chunks received yet AND stream is active"
  heuristic. We pick the local heuristic to keep the change
  frontend-only: when `streamStatus[s] === "active"` AND no
  `transcript_chunk` for stream `s` has yet been received within the
  first 8 seconds, treat as `connecting`. Otherwise `active` →
  `speaking` if recent chunks within ~2s, else `listening`. `silence`
  → `listening`. `stopped` → renders no bars (consistent with today's
  muted state).

Backend message shape is unchanged. The decision keeps the change PR-sized
and avoids a parallel meeting-session message change.

**Alternative considered:** drive the three states off a new
`stream_state` WebSocket message. Rejected — couples to backend, lifts
this change out of the effect-layer bucket.

### Transcript animated list keeps DOM contract, only swaps the entry animation

magicui `animated-list` provides a wrapper that fades-in / lifts-in
children as they mount. We import the pattern, not the package, because
our chunk renderer already uses `framer-motion`'s `AnimatePresence`
elsewhere. The new behavior:

- Each `<TranscriptChunkRow>` mounts with an `initial = { opacity: 0,
  y: 8 }`, `animate = { opacity: 1, y: 0 }` variant.
- A new `prefers-reduced-motion` hook returns `true` → animation is
  skipped, chunks render at final frame.
- The existing `data-testid="transcript-chunk"`, `data-speaker`, and
  per-chunk action menu wire is untouched.

We DO NOT animate chunk-level scroll position; auto-scroll to bottom
remains the current `scrollIntoView` behavior.

### elevenlabs adoption is spike-gated

We do not pre-commit to adopting elevenlabs `transcript-viewer` or
`bar-visualizer` packages. Apply phase opens with a spike task per
component:

- Check whether the elevenlabs UI components are published to npm under
  a permissive (MIT / Apache-2.0 / similar) license.
- If yes → add the package, wrap in our token-consuming variant, ship.
- If no → extract the visible pattern (DOM shape, ARIA wiring, motion
  curves) into a local component named identically (`<BarVisualizer>`,
  `<TranscriptViewer>`) so consumer code is decoupled from the source.

The spike outcome is recorded as a one-line note in `tasks.md` under
the relevant task. No further design.md update required.

### vengenceui glass-dock follows the same spike-then-decide path

Same logic as elevenlabs. License + install path verified in a spike
task; if not adoptable we extract the visible pattern (backdrop blur,
inner border highlight, rounded pill shape, subtle ambient shadow)
into a local component matching the DESIGN.md description.

### uiverse ports each get their own task

uiverse snippets cannot be installed. Each port (cuddly-catfish-6 hover
glow, pink-chicken-70 button hover, curvy-earwig-22 input, spicy-rat-83
reveal) becomes a dedicated task whose acceptance criterion is "a
React + Tailwind + Aura token component that visually matches the
snippet with no raw hex in className". Ports keep the motion behavior
but recolor to our token palette (purple as primary, no third-party
brand colors).

## Implementation Contract

**Behavior**

- A user on a protected route in dark mode with `prefers-reduced-motion`
  unset sees a subtle stars layer behind page content. A user in light
  mode or with `prefers-reduced-motion: reduce` sees no stars and pays
  no animation frame cost.
- A user opening a meeting in `in_progress` state sees the capture
  indicator render exactly one of three labeled states per stream
  (`Connecting` / `Listening` / `Speaking`) with the corresponding
  Aura-token color (warning / `me` blue / `them` pink) and motion
  (orange slow pulse / flat baseline / pulsing amplitude).
- A user watching the transcript stream sees each new chunk
  fade-in-and-lift on mount. With `prefers-reduced-motion`, the chunks
  appear instantly at their final position.
- A user hovering a meeting card on the meetings list sees a subtle
  border glow + lift; the existing tag-picker hover affordance remains
  visible at top-right.
- A user clicking a primary CTA button sees the ported pink-chicken
  motion (recolored to Aura purple). Disabled buttons render with the
  existing muted style and no motion.
- A user filling a `variant="curvy"` text input sees the label float
  + underline animation. Other inputs (`variant="default"`) are
  unchanged.
- After a successful upload, export, or settings save, the user sees
  a brief `<SuccessResult>` micro-interaction. Reduced-motion users see
  the final "check" frame immediately.
- The first time the user opens a freshly-generated playbook, the
  playbook content area performs a one-shot reveal animation
  (spicy-rat-83 derived). A persisted flag (localStorage,
  `playbookRevealSeen:<meetingId>`) prevents replay on subsequent
  visits.
- The mini-player chrome reads as a floating glass dock.

**Interface / data shape**

- New components export from `packages/web/src/components/`:
  - `animate-ui/backgrounds/stars.tsx` → `<Stars />`
    Props: none. Self-gates on theme + reduced-motion.
  - `magicui/animated-list.tsx` → `<AnimatedList>` + `<AnimatedListItem>`
    Props: `children`, `delay?` (default 60ms stagger).
  - `ui/bar-visualizer.tsx` → `<BarVisualizer>`
    Props: `state: "connecting" | "listening" | "speaking" | "off"`,
    `tone: "me" | "them" | "warning"`, `barCount?` (default 10),
    `ariaLabel: string`.
  - `ui/glass-dock.tsx` → `<GlassDock>`
    Props: `children`, `className?`. Renders a `position: fixed`-ready
    container; caller positions.
  - `ui/hover-glow-card.tsx` → `<HoverGlowCard>`
    Props: `children`, `className?`, `asChild?: boolean`.
  - `ui/success-result.tsx` → `<SuccessResult>`
    Props: `message: string`, `onAnimationComplete?: () => void`.
  - `ui/spicy-reveal.tsx` → `<SpicyReveal>`
    Props: `children`, `revealKey: string` (used as localStorage key).
- `Input` gains `variant?: "default" | "curvy"`. Default unchanged.
- `Button` gains a `data-cta="primary"` selector that triggers the
  ported hover motion, OR a new `<PrimaryCtaButton>` wrapper —
  implementer's choice during apply, both satisfy the contract.

**i18n contract**

- `meetings.session.barVisualizer.connecting` — zh-TW + en
- `meetings.session.barVisualizer.listening` — zh-TW + en
- `meetings.session.barVisualizer.speaking` — zh-TW + en
- Any other user-visible string introduced (e.g., success result toast,
  spicy reveal accessibility label) lands in both locales.

**Failure modes**

- elevenlabs package not adoptable → local extract ships with same
  component names and props. No downstream consumer change.
- vengenceui glass-dock not adoptable → local extract ships.
- `prefers-reduced-motion: reduce` → all motion-heavy components
  return their final visual state without animation.
- Server emits unexpected `streamStatus` → `<BarVisualizer state="off">`
  renders a static muted baseline (existing `stopped` behavior).

**Acceptance criteria**

- New CaptureIndicator emits `data-state` ∈ {`connecting`, `listening`,
  `speaking`, `off`} per stream; tests assert each state branch.
- Reduced-motion tests assert no `animation-name` / `transition`
  styles applied (or component skips motion variants).
- Locales test (`locales.test.ts`) passes — both files deep-equal.
- `<Stars />` renders `null` in light mode (snapshot test).
- `<HoverGlowCard>` className strings contain zero hex literals
  (regex assertion in design-system audit test).
- `transcript-pane.test.tsx` still passes (DOM contract preserved).
- meeting-session capture-indicator scenarios still pass with the new
  three-state mapping.

**Scope boundaries**

- IN scope: the eight new component files, the three modified consumer
  files (transcript-pane, capture-indicator, meeting-card), the
  three new i18n keys × 2 locales, the spec deltas.
- OUT of scope: routing changes, primitive rewrites, token edits,
  backend changes, S27 files, second / third glass dock wirings,
  rolling `variant="curvy"` across all forms.

## Risks / Trade-offs

- [Risk] Animated list + framer-motion increases bundle size →
  Mitigation: framer-motion is already in the dependency graph
  (`transcript-pane` already imports it). Net new weight is the small
  list wrapper component.
- [Risk] uiverse snippets are visually inconsistent across browsers
  → Mitigation: each port has a manual visual check task on Chrome +
  Safari before close-out; only motion patterns are ported, never raw
  colors.
- [Risk] elevenlabs / vengenceui upstream packages may be source-only
  or under restrictive licenses → Mitigation: spike-gated; local
  extract pattern matches the public DOM/props so consumer code is
  insulated either way.
- [Risk] Stars layer paints on every protected route, increasing GPU
  cost on low-end devices → Mitigation: gate on `prefers-reduced-motion`
  and (future) a settings opt-out; the component is throttled to a
  modest star count (≤ 60).
- [Risk] CaptureIndicator state mapping via "no chunks for 8s →
  connecting" heuristic could false-positive when a real silence
  precedes the first chunk → Mitigation: heuristic only applies on
  the first 8s of stream lifetime; once any chunk arrives for the
  stream, the heuristic disables and only `streamStatus` drives state.
- [Risk] Spicy reveal animation could feel out of place if Sean
  rejects the playbook completion placement → Mitigation: design
  review checkpoint before apply; component is generic and easy to
  re-wire.

## Migration Plan

- Land the new components behind the existing protected-shell + meeting
  pages without removing anything. No feature flag needed; the work is
  visual.
- Existing tests assert structural contracts (`data-testid`, DOM
  shape, locales parity) and continue to pass.
- Rollback strategy: revert the apply commits. No persisted state
  (other than the localStorage `playbookRevealSeen:*` flag, which is
  client-side and self-recovers).

## Open Questions

- **Glass dock wiring** — confirm Sean is OK with mini-player as the
  first wiring (vs. in-meeting toolbar).
- **Spicy reveal placement** — confirm playbook-generation completion
  vs. fallback to export-download.
- **elevenlabs install spike** — outcome recorded inline during apply.
- **vengenceui install spike** — outcome recorded inline during apply.

