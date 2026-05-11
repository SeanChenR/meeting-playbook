## ADDED Requirements

### Requirement: TranscriptPane SHALL render speaker contrast via all four visual cues simultaneously

The `TranscriptPane` component in `packages/web/src/components/transcript-pane.tsx` SHALL render each transcript chunk with the four visual cues from `ui-design-system` (3px left border, tinted background, speaker dot, semibold coloured name) — not the slice-7 single-border-only treatment.

The `data-speaker` attribute on each chunk wrapper SHALL be preserved (`"me"` | `"counterparty"`) so existing e2e selectors continue to resolve. The CSS class names that drove the slice-7 styling (e.g. `border-l-(--color-muted-foreground)`, `border-l-(--color-primary)`) SHALL be replaced by `border-l-(--color-me)` / `border-l-(--color-them)` tokens introduced in `ui-design-system`.

A `data-testid="speaker-dot"` element SHALL be inserted before each speaker name. Speaker names SHALL render with `font-weight: 600` in `--color-me` / `--color-them` (not the slice-7 muted-foreground).

The pane SHALL accept a new optional `contrastLevel?: "subtle" | "strong"` prop driven by the design-system tweak panel; when `"strong"` (default for production), the tint alphas SHALL come from the `[data-transcript-contrast="strong"]` overrides (`--me-tint-alpha: 0.14`, `--them-tint-alpha: 0.20`) declared in `ui-design-system`.

#### Scenario: Counterparty chunk renders all four cues plus data-testid speaker-dot

- **GIVEN** the transcript pane renders a chunk with `speaker = "counterparty"`, `name = "林經理"`, `text = "..."`
- **WHEN** the rendered DOM is inspected
- **THEN** the chunk wrapper SHALL have `data-speaker="counterparty"` AND `border-left-color` SHALL resolve to `--color-them` AND the inner content SHALL contain `[data-testid="speaker-dot"]` with background `--color-them` AND the speaker name element SHALL have `font-weight: 600` and colour `--color-them`

#### Scenario: Existing data-speaker selectors keep working

- **GIVEN** the e2e harness queries `[data-speaker="counterparty"]` to locate counterparty chunks
- **WHEN** the new TranscriptPane renders after this overhaul
- **THEN** the query SHALL still resolve to the same chunk wrapper elements (selector stability preserved across the visual rewrite)

### Requirement: TranscriptPane re-run overlay SHALL animate in with framer-motion

The slice-11 re-run progress overlay (the skeleton + `重新轉錄中… (n/m chunks)` panel that appears while `meeting.rerun_asr_pending === true` OR polled `rerunStatus.status === "pending"`) SHALL animate in via framer-motion's `AnimatePresence` using the shared `paneEnter` preset (4px translateY + opacity, 180ms ease-out). When the polled status transitions to `idle`, the overlay SHALL animate out (reverse) before unmounting.

The progress counter inside the overlay SHALL use `magicui` `NumberTicker` for the `chunks_processed` numeral so the count change feels alive (tick from previous value to new value). The denominator (`chunks_total`) SHALL render as plain text since it changes at most once per task.

`data-testid="transcript-rerun-overlay"` SHALL remain on the overlay root element so existing component tests resolve it.

#### Scenario: Overlay animates in on rerun pending

- **GIVEN** the meeting is `rerun_asr_pending = false` AND the user has just clicked `重新轉錄`
- **WHEN** the meeting GET refetch returns `rerun_asr_pending = true`
- **THEN** the transcript pane SHALL render `[data-testid="transcript-rerun-overlay"]` with an enter animation (opacity 0 → 1, y 4 → 0 over ~180ms); without `prefers-reduced-motion` this SHALL be visible to the eye

#### Scenario: NumberTicker animates the chunks_processed numeral

- **GIVEN** the overlay is visible AND polled status reports `chunks_processed = 3, chunks_total = 10`
- **WHEN** the next poll reports `chunks_processed = 4`
- **THEN** the rendered numeral 3 SHALL animate up to 4 via `magicui` NumberTicker (not flash-replace) AND the slash + total `/10 chunks` SHALL re-render unchanged

### Requirement: ChatBubble component SHALL replace flat advisor message list

The advisor pane (`packages/web/src/components/advisor-pane.tsx`) SHALL render the chat history using a new `ChatBubble` component supporting `role: "user" | "assistant"`:

- `role="user"`: right-aligned, background `--color-primary`, foreground `--color-primary-foreground`, border-radius `var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)`, max-width 85%.
- `role="assistant"`: left-aligned, background `--color-surface-2`, foreground `--color-foreground`, border-radius `var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px`, 1px border in `--color-border`, max-width 85%.

Below the message list, a row of suggestion `Chip` buttons SHALL appear when the advisor is idle (`下一步該說什麼？` / `對方真正在意什麼？` / `幫我準備 closing` — pulled from the new `meetings.advisor.suggestions.*` i18n group). Clicking a chip SHALL prefill the input with that text and focus the input.

The input row SHALL stick to the bottom of the pane (matching the design bundle), with a single-line `<input>` flanked by a `Button` variant=`primary` size=`sm` icon=`Send` that submits on click or Enter keydown.

#### Scenario: User message renders right-aligned with primary background

- **GIVEN** the advisor pane has a message with `role = "user"` and `text = "如果他壓我先給 7% 怎麼辦？"`
- **WHEN** the message is rendered
- **THEN** the bubble SHALL have `align-self: flex-end` (or equivalent flex container property) AND background colour resolving to `--color-primary` AND foreground resolving to `--color-primary-foreground` AND `max-width: 85%`

#### Scenario: Suggestion chips prefill the input

- **GIVEN** the advisor pane is idle (no in-flight `request_advice`)
- **WHEN** the user clicks the chip labelled `下一步該說什麼？`
- **THEN** the input element SHALL receive focus AND its value SHALL be set to the chip text (allowing the user to edit before submitting)
