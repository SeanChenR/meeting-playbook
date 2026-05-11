## ADDED Requirements

### Requirement: MetadataCard SHALL render as a two-column layout with embedded CaptureIndicator

The meeting metadata card at the top of `/meetings/$id` SHALL be split into two horizontal regions inside a single `Card`:

- **Left column** (flex: `1 1 320px`): status badge row (e.g. `進行中` / `已結束` / `已排程` with coloured dot, plus `建立 5/12 02:30 · 第 N 次重新轉錄` micro-copy when applicable) → meeting title at `--text-2xl` font-weight 700 → metadata grid (`grid-template-columns: auto 1fr`) carrying 對方 / 我方 / 錄音 rows with mini avatars.
- **Right column** (flex: `0 0 280px`): `Label`-prefixed `Select` for the ASR engine with the persistent hint `切換下一場會議生效` (using the new shadcn Select primitive, NOT the native `<select>`) → `CaptureIndicator` widget below it.

`CaptureIndicator` SHALL be embedded inside the right column of the metadata card (not a separate full-width row as in slice-7) and SHALL render two `CaptureRow` entries (one for the microphone-sourced 我方 stream, one for the BlackHole-sourced 對方 stream). Each row SHALL include a `Dot` (pulsing red while `recording === true`) + label text + a horizontal sparkline of bars whose heights animate as audio frames arrive.

A `Separator` SHALL divide the two-column region from the action bar.

The action bar SHALL render below the separator with the following layout: `[開始會議]` or `[結束會議]` (mutually exclusive based on `recording` state) → `[重新轉錄]` (only when status === "completed" && recordings_available && !rerun_asr_pending) → flex spacer → `[匯出 .md]` → `[刪除]`. Action buttons SHALL use the new shadcn `Button` variants (`primary` / `secondary` / `ghost` / `danger`) — not bare HTML buttons or the slice-7 button styles.

#### Scenario: Right column shows ASR Select and CaptureIndicator together

- **GIVEN** the meeting detail page with status === "in_progress" and recording === true
- **WHEN** the MetadataCard is rendered
- **THEN** the right column SHALL contain a `data-testid="asr-provider-selector"` Select element AND below it a CaptureIndicator with exactly two CaptureRow entries (one labelled 麥克風 / 我方, one labelled 系統音訊 / 對方), each row including a pulsing dot

#### Scenario: Action bar uses shadcn Button variants

- **GIVEN** the meeting detail page after this change ships
- **WHEN** the action bar buttons are rendered
- **THEN** every action button SHALL be an instance of the shadcn `Button` component (importable from `packages/web/src/components/ui/button.tsx`) AND none SHALL use inline `style={{ background: ... }}` for cosmetic colours

#### Scenario: Recording badge and rerun gating coexist correctly

- **GIVEN** a meeting with status === "completed" AND recordings_available === true AND rerun_asr_pending === false
- **WHEN** the metadata card is rendered
- **THEN** the 錄音 row in the metadata grid SHALL show `Dot` (tone="success") + 「可用 · {duration}」 AND the action bar SHALL include a visible `[重新轉錄]` button

### Requirement: Workspace layout SHALL switch between three-column and stacked via animate-ui transition

The workspace area below the `Tabs` selector SHALL provide a `LayoutSwitcher` (icon-only segmented button group, top-right of the tab bar) with two modes:

- `cols` (default): three columns with `grid-template-columns: minmax(260px, 0.8fr) minmax(360px, 1.2fr) minmax(280px, 0.9fr)` and 12px gap.
- `rows`: three rows with `grid-template-rows: minmax(180px, 0.9fr) minmax(220px, 1.2fr) minmax(180px, 0.9fr)` and 12px gap.

The layout choice SHALL be persisted to `localStorage.mp-detail-layout` (keyed per user is acceptable but not required). Switching layouts SHALL animate via `animate-ui` layout transition (reorder + size morph, 250ms), respecting `prefers-reduced-motion`.

Each pane (`PlaybookPane` / `TranscriptPane` / `AdvisorPane`) SHALL be wrapped in a shared `Pane` component declaring `title`, optional `badge`, optional `actions`, and optional `accent` (3px coloured strip beside the title). All three panes SHALL share the same shell style: `--color-surface` background, 1px border in `--color-border`, `--radius-lg` corners, `--shadow-sm`, overflow auto in the body.

#### Scenario: Layout switcher persists choice across reload

- **GIVEN** the user is on `/meetings/$id` with `cols` layout
- **WHEN** the user clicks the `rows` icon in the LayoutSwitcher
- **THEN** the workspace SHALL re-grid to three stacked rows AND `localStorage.mp-detail-layout` SHALL equal `"rows"` AND a reload of the page SHALL re-render in `rows` mode

#### Scenario: Layout transition animates with animate-ui

- **GIVEN** the workspace is in `cols` mode and `prefers-reduced-motion` is NOT set
- **WHEN** the user clicks the `rows` icon
- **THEN** the three panes SHALL animate their position and size over ~250ms (not jump) AND the animation SHALL be powered by `animate-ui` layout-transition primitives (verifiable by inspecting the package being imported in `detail.tsx`)

### Requirement: Tab content SHALL cross-fade via framer-motion

When the user switches between `工作區` and `摘要` tabs on the detail page, the visible content SHALL cross-fade (exit 100ms, enter 150ms) using framer-motion's `AnimatePresence` + the `tabContent` preset from `lib/motion-presets.ts`. The active tab SHALL be indicated by the shared `Tabs` primitive's active state (background `--color-surface` + shadow-sm) rather than a custom border indicator.

#### Scenario: Switching from Workspace to Summary cross-fades content

- **GIVEN** the user is on the `工作區` tab
- **WHEN** the user clicks the `摘要` tab
- **THEN** the workspace 3-pane region SHALL fade out over 100ms AND the summary markdown card SHALL fade in over 150ms AND the active tab indicator SHALL move via the radix-tabs underlying animation

#### Scenario: Summary tab is gated by meeting status

- **GIVEN** a meeting with status !== "completed"
- **WHEN** the Tabs primitive renders
- **THEN** the `摘要` tab trigger SHALL render with `data-disabled` attribute AND clicking it SHALL not change the active tab; the workspace tab content SHALL remain visible
