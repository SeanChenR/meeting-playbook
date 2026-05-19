## 1. Spikes and shared infrastructure

- [x] 1.1 Land a single `useReducedMotion` hook (or equivalent) under `packages/web/src/hooks/` so every effect-layer component honors prefers-reduced-motion through one canonical source; verified by unit test asserting the hook returns `true` when `matchMedia('(prefers-reduced-motion: reduce)').matches` is mocked true and updates on `change` events.
- [x] 1.2 elevenlabs adoption is spike-gated — record the install + license outcome for `transcript-viewer` and `bar-visualizer` as a one-line note in this tasks file under this checkbox, then either add the package or fall back to the local-extract pattern named in design.md; verified by a follow-up task marking the chosen path.
  - SPIKE OUTCOME: `@elevenlabs/react` exists on npm (MIT) but only ships the voice-agent SDK; `transcript-viewer` and `bar-visualizer` live as docs-site snippets at `ui.elevenlabs.io`, not as an installable component package. Decision: **local extract** — both ports are ported into our codebase as `<BarVisualizer>` with Aura tokens. (No standalone `<TranscriptViewer>` ships in P3 — the transcript-viewer pattern is realised via the animated-list adoption inside `transcript-pane.tsx`.)
- [x] 1.3 vengenceui glass-dock follows the same spike-then-decide path — record install + license outcome and pick adopt vs. local extract; verified by an entry recorded in this tasks file.
  - SPIKE OUTCOME: `vengenceui` / `@vengenceui/glass-dock` is not published to npm (404). Decision: **local extract** — `<GlassDock>` is ported as a generic Aura-token container (backdrop-blur + inner border highlight + rounded + ambient shadow).
- [x] 1.4 Add the three new i18n keys `meetings.session.barVisualizer.{connecting,listening,speaking}` to BOTH `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json`; verified by `bun --filter @meeting-playbook/web test packages/web/src/locales/locales.test.ts` passing (deep-equal locale parity).

## 2. Stars background

- [x] 2.1 Ship `<Stars />` honoring the "Stars background lives inside the protected shell, dark + motion only" decision and the "Stars background SHALL mount only on protected routes in dark mode" requirement — component returns `null` in light mode, reduced-motion mode, or public routes; verified by component tests covering the four gate combinations (dark + motion / dark + reduced / light + motion / public-route).
- [x] 2.2 Mount `<Stars />` inside `<ProtectedShell>` behind `<main>` so page content paints on top; verified by `packages/web/src/components/protected-shell.test.tsx` asserting stars sibling is present in dark + motion-allowed mode and absent otherwise.

## 3. CaptureIndicator three-state bar visualizer

- [x] 3.1 Implement the standalone `<BarVisualizer>` component delivering the "Bar visualizer SHALL be a reusable Aura-token component independent of CaptureIndicator" requirement — accepts `state`, `tone`, `barCount`, `ariaLabel`; exposes `role="img"` + `aria-label`; verified by unit tests covering each `state` × `tone` combination and an a11y assertion on the accessible name.
- [x] 3.2 Rewrite `capture-indicator.tsx` per the "CaptureIndicator becomes a three-state bar visualizer" decision so the "CaptureIndicator SHALL render one of four discrete states per stream" requirement is satisfied — implement the state-derivation table (active+no-chunks-8s → connecting, active+recent-chunk → speaking, active+stale → listening, silence → listening, stopped/ending → off); verified by `packages/web/src/components/capture-indicator.test.tsx` asserting `data-state` outputs for each row in the example table.
- [x] 3.3 Use the new i18n keys from task 1.4 as the visible / accessible labels for each state; verified by a test asserting the rendered text resolves via `t("meetings.session.barVisualizer.<state>")` for at least one row.

## 4. Transcript animated list

- [x] 4.1 Land `<AnimatedList>` + `<AnimatedListItem>` under `packages/web/src/components/magicui/animated-list.tsx` delivering the "Transcript animated list keeps DOM contract, only swaps the entry animation" decision; verified by a unit test that mounts three items and asserts the first item finishes its motion variant before the third (or, under reduced motion, asserts no transition styles).
- [x] 4.2 Adopt the animated-list pattern inside `transcript-pane.tsx` so the "Transcript chunks SHALL fade-in on mount via the animated-list pattern" requirement is satisfied — preserve `data-testid="transcript-chunk"`, `data-speaker`, and action-menu wiring; verified by `packages/web/src/components/transcript-pane.test.tsx` continuing to pass and a new test asserting fade-in variants are present (and skipped under reduced motion).

## 5. Glass dock

- [x] 5.1 Implement `<GlassDock>` per the "Glass dock SHALL be a reusable container with one initial wiring" requirement — backdrop-blur, token-driven border / radius (`--radius-lg`) / shadow, generic `children` + optional `className`; verified by snapshot + a className regex test asserting no raw hex literals.
- [x] 5.2 Wire `<GlassDock>` once per the "Glass dock ships with exactly one initial wiring; remaining placements deferred" decision — wrap the mini-player chrome inside `meeting-audio-mini-player.tsx`; verified by `meeting-audio-mini-player.test.tsx` asserting the outer wrapper is a `<GlassDock>` instance.

## 6. Hover and interaction effect ports

- [x] 6.1 Port `cuddly-catfish-6` into `<HoverGlowCard>` (or equivalent className composition) delivering the "Card hover glow SHALL be a reusable composition consumed by meeting cards" requirement — uiverse ports each get their own task per design.md; verified by a unit test asserting hover transitions exist and zero raw hex literals appear in the className strings.
- [x] 6.2 Adopt `<HoverGlowCard>` inside `meeting-card.tsx` while keeping the existing tag-picker hover affordance visible; verified by `meeting-card.test.tsx` covering both hover state and tag-picker visibility.
- [x] 6.3 Port `pink-chicken-70` motion onto primary CTAs per the "Primary CTA buttons SHALL expose the ported hover motion variant" requirement — either `data-cta="primary"` on `<Button>` or a `<PrimaryCtaButton>` wrapper; recolor stays Aura purple; verified by a button test asserting the hover motion engages on enabled primary CTAs and is suppressed on disabled buttons.
- [x] 6.4 Port `curvy-earwig-22` into the `<Input>` component as `variant="curvy"` so the "Inputs SHALL expose a curvy variant for opt-in adoption" requirement is met — default variant DOM and behavior are unchanged; verified by snapshot of the default variant matching pre-change and a new test asserting the curvy variant floats the label on focus.
- [x] 6.5 Adopt `ui.devsloka.in` success-result as `<SuccessResult>` per the "Success result overlay SHALL ship as a reusable micro-interaction" requirement and wire it as the completion transition for the staged-attachment dropzone; verified by a test asserting the check glyph + localized message render on dispatch and `onAnimationComplete` fires under reduced motion within one tick.
- [x] 6.6 Port `spicy-rat-83` into `<SpicyReveal>` and wire it to the playbook content area per the "Spicy-rat-83 reveal wires to playbook generation completion" decision and the "Spicy reveal SHALL ship as a one-shot, persisted reveal animation" requirement — first open plays once, `localStorage["playbookRevealSeen:<meetingId>"]` is set, re-opens skip the animation; verified by a unit test simulating first-open and re-open against a mocked localStorage.

## 7. Cross-cutting compliance and a11y

- [x] 7.1 Enforce the "All effect-layer motion SHALL honor prefers-reduced-motion" requirement across every new component — each component file imports and consults the shared hook from task 1.1; verified by a grep-based test asserting every new effect-layer file references the hook (or a centralized `motion-safe` className) and by component tests covering the reduced-motion branch.
- [x] 7.2 Enforce the "Effect-layer components SHALL consume Aura tokens via CSS variables only" requirement — add a design-system audit test that greps the new component files for `#[0-9a-fA-F]{3,8}` and `rgb(` / `rgba(`; verified by the audit test returning zero matches.

## 8. Verification and rollout

- [x] 8.1 Run the full web test suite — `bun --filter @meeting-playbook/web test` — and confirm every pre-existing meeting-session, transcript-pane, capture-indicator, meeting-card, and protected-shell test passes alongside the new tests for the effect-layer components.
- [ ] 8.2 Manual verification pass on Chrome + Safari in both dark and light themes plus a reduced-motion run — confirm stars render only in dark + motion-allowed mode, capture-indicator transitions through `connecting → listening → speaking` states during a real session, transcript chunks fade-in, glass-dock-wrapped mini-player reads correctly, meeting cards hover, primary CTAs animate, curvy input variant animates label + underline, success result fires on attachment upload completion, and spicy reveal plays once on first playbook open; verified by a manual checklist recorded in the apply commit body.
  - DEFERRED to merge owner: this branch is held uncommitted pending Sean's manual review (per worktree constraint — no commit or push from apply agent). The 23-task automated suite is green; the visual pass belongs to the merge gate after rebase on P1 tokens so the new `--color-*` variables resolve.

