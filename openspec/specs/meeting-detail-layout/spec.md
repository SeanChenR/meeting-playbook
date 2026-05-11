# meeting-detail-layout Specification

## Purpose

Defines how the meeting detail page (`/meetings/{id}`) arranges its three core
panes — Playbook, Transcript, and Advisor — together with the meeting meta
card. The page exposes a layout switcher that lets the user toggle between a
vertical Stack mode and a three-column Columns mode (30/40/30 grid); the
choice is persisted to `localStorage` under `meeting-detail.layout` so it
survives reloads. Columns mode is the default.

To support the edge-to-edge column grid, the shared `ProtectedShell`
component accepts a `fullBleed` prop that disables its centered max-width
container. The detail page is the sole route that opts in. In Columns mode
the three panes share an equal computed height derived from the viewport
(roughly `calc(100vh - 220px)`) so the row of columns presents as a balanced
grid rather than a jagged silhouette; each pane scrolls independently.
Stack mode preserves natural per-pane heights.

## Requirements

### Requirement: Detail page exposes a layout switcher persisted across sessions

The meeting detail page SHALL render a layout switcher control with two modes: `stack` (vertical) and `columns` (three-column). The selected mode SHALL persist in `localStorage` under the key `meeting-detail.layout`. On initial load when the key is unset or holds an invalid value, the layout SHALL default to `columns`. The switcher SHALL be rendered in the page top bar to the right of the back-link, MUST be reachable by keyboard, and MUST update the rendered layout immediately when toggled (no page reload).

#### Scenario: Switching layout persists and survives reload

- **GIVEN** a user opens `/meetings/{id}` with no prior layout preference
- **WHEN** the user clicks the Stack icon button in the top bar
- **THEN** the page SHALL re-render in stack mode immediately, and `localStorage["meeting-detail.layout"]` SHALL equal `"stack"`; reloading the page SHALL render the page in stack mode

#### Scenario: Invalid stored value falls back to columns

- **GIVEN** `localStorage["meeting-detail.layout"]` holds the string `"weird-value"`
- **WHEN** the user opens `/meetings/{id}`
- **THEN** the page SHALL render in columns mode (the default), without throwing

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Columns mode renders three panes in a 30/40/30 grid with full-width meta

In columns mode the meeting detail page SHALL render three vertical panes side-by-side: Playbook (30% width), Transcript (40% width), and Advisor (30% width). The meeting meta card (title, status pill, Start/End buttons, capture indicator) SHALL render as a full-width horizontal bar above the columns and SHALL NOT be placed inside any column. The grid widths SHALL be fixed (no drag-resize). Each column SHALL scroll independently of the others.

#### Scenario: Columns mode applies the fixed 30/40/30 grid

- **GIVEN** the page is in columns mode and the viewport is wider than 1024px
- **WHEN** the page renders
- **THEN** the three column wrappers SHALL have CSS computed widths in the proportions 30%, 40%, and 30%, and the meta card SHALL span the full content width above them

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Stack mode renders the three panes vertically in P-T-A order

In stack mode the meeting detail page SHALL render the same three panes one above another in the order Playbook → Transcript → Advisor (top to bottom). The meeting meta card SHALL render above all three. Each pane SHALL be full content width.

#### Scenario: Stack mode renders the panes in order

- **GIVEN** the page is in stack mode
- **WHEN** the page renders
- **THEN** in document source order the Playbook pane SHALL appear before the Transcript pane, which SHALL appear before the Advisor pane, all full-width

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Advisor pane shows a placeholder until the tactical advisor capability ships

The Advisor pane SHALL render the real `<AdvisorPane>` component (per the `tactical-advisor` capability spec) in both layout modes when the meeting session phase is `in_progress`. The placeholder text introduced in slice-7 round 1 (`meetings.detail.advisorPlaceholder`) is RETIRED — it MUST NOT appear once the meeting reaches `in_progress` phase. When the session phase is NOT `in_progress` (idle / connecting / ended / error), the pane SHALL render the empty-state hint described in the `tactical-advisor` spec (data-testid `advisor-pane-empty`) so the column never collapses to nothing in the columns layout.

#### Scenario: in_progress meeting renders the real AdvisorPane

- **GIVEN** a meeting whose WebSocket session has reached `in_progress`
- **WHEN** the detail page renders in either columns or stack mode
- **THEN** the Advisor pane SHALL contain a `Get Advice` button (per `tactical-advisor` spec) and SHALL NOT contain the legacy placeholder string from `meetings.detail.advisorPlaceholder`

#### Scenario: idle meeting still keeps the column populated with the empty state

- **GIVEN** a meeting in `scheduled` status whose session has not started
- **WHEN** the detail page renders in columns mode
- **THEN** the Advisor pane SHALL contain an element with `data-testid="advisor-pane-empty"` so the right column has visible content; it SHALL NOT contain a `Get Advice` button


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: ProtectedShell exposes a fullBleed prop that disables the centered max-width container

The `ProtectedShell` component SHALL accept an optional `fullBleed?: boolean` prop defaulting to `false`. When `fullBleed` is `false`, the shell SHALL preserve its existing centered max-width content container. When `fullBleed` is `true`, the shell SHALL render its content area without a max-width constraint, allowing the page to occupy the full browser viewport width. The detail page SHALL always pass `fullBleed`. List, new, login, signup, home, and calendar-import routes SHALL NOT pass it.

#### Scenario: Detail page renders edge-to-edge

- **WHEN** the user opens `/meetings/{id}`
- **THEN** the rendered content area SHALL have no max-width style applied at the shell level, allowing nested layouts (columns or stack) to use the full viewport width

#### Scenario: Other routes keep the centered container

- **WHEN** the user opens `/meetings`
- **THEN** the rendered content area SHALL be wrapped in the existing centered max-width container

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Columns mode three panes share equal visible height (slice-7 round 2)

In columns mode on viewports >=1024px, the three content panes (Playbook, Transcript, Advisor) SHALL render at IDENTICAL visible height, so the row of columns presents as a balanced grid rather than a jagged silhouette. The shared height SHALL be derived from the available viewport height minus the header + meta-card stack (target: `calc(100vh - 220px)` give-or-take a few pixels). Content overflow within any pane SHALL be confined to that pane's own scroll container so a long transcript does not push other panes downward.

The equal-height constraint SHALL apply ONLY in columns mode. Stack mode preserves natural per-pane heights (vertical layout doesn't suffer the imbalance issue).

#### Scenario: Columns mode panes are visually balanced

- **GIVEN** detail page in columns mode on a 1440-wide viewport with a tall transcript and a short playbook
- **WHEN** the page renders
- **THEN** the three pane wrappers (`data-testid="detail-pane-playbook"`, `detail-pane-transcript`, `detail-pane-advisor`) SHALL have equal computed heights (within 1px tolerance), and each pane's internal scroll SHALL be independent

#### Scenario: Stack mode preserves natural heights

- **GIVEN** detail page in stack mode with mixed-length pane content
- **WHEN** the page renders
- **THEN** each pane SHALL size to its own content (no fixed height applied); the equal-height constraint MUST NOT activate

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: AdvisorPane integrates chat history hydration via React Query

The detail page's right column SHALL mount `<AdvisorPane session={session} />` with the session hook providing chat-history-aware state. The page SHALL use React Query to fetch `GET /api/meetings/{id}/chat_messages` via `chat-api.ts`'s `chatMessagesQueryOptions(meetingId)` on detail page mount. When the query resolves, the response SHALL be passed into the `useMeetingSession` hook (or hydrated into its reducer via a `HISTORY_LOADED` action) so that the rendered AdvisorPane has the persisted history before the user takes any action.

After every successful advise stream (signalled by an `advice_done` frame), the hook SHALL invalidate the React Query cache key `["chat_messages", meetingId]` so the history list re-fetches and reflects the newly persisted pair. The cache SHALL stay valid across the entire detail page lifetime; navigating away and back SHALL show cached data immediately while a background refetch verifies freshness.

#### Scenario: Detail page mount triggers chat_messages GET

- **GIVEN** a navigation to `/meetings/{m_id}` for a meeting with persisted chat history
- **WHEN** the detail page mounts and React Query bootstraps
- **THEN** the network SHALL contain a GET `/api/meetings/{m_id}/chat_messages` request; on success, the AdvisorPane SHALL render the persisted message bubbles before any WS interaction

#### Scenario: Successful advice stream invalidates chat_messages cache

- **GIVEN** an `in_progress` meeting and an active session with no in-flight advice
- **WHEN** the user sends a chatbox message that completes successfully (`advice_done` received)
- **THEN** the React Query cache key `["chat_messages", m_id]` SHALL be invalidated; a fresh GET `/api/meetings/{m_id}/chat_messages` SHALL fire; the new history list SHALL include the just-persisted user + advisor pair

<!-- @trace
source: slice-09-advisor-chatbox
updated: 2026-05-11
code:
  - packages/web/src/lib/session-ws.ts
  - docs/agents/advisor.md
  - packages/backend/meeting_playbook/chat/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/web/src/locales/en.json
  - packages/backend/alembic/versions/0005_create_chat_message.py
  - packages/web/src/lib/chat-api.ts
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/components/chat-input.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/backend/meeting_playbook/advisor/base.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - packages/backend/meeting_playbook/chat/__init__.py
  - packages/backend/meeting_playbook/chat/repository.py
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/chat/router.py
tests:
  - packages/web/src/lib/chat-api.test.ts
  - packages/web/src/lib/session-ws.test.ts
  - packages/backend/tests/chat/test_repository.py
  - packages/web/src/components/chat-message-list.test.tsx
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/test_alembic_chat_message.py
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/chat/test_router.py
  - packages/backend/tests/chat/__init__.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/backend/tests/conftest.py
-->

---
### Requirement: Detail page wraps existing workspace in a Tabs UI with a gated Summary tab

The meeting detail page SHALL wrap the existing three-column workspace inside a Tabs primitive with two tabs: `workspace` (default active, shows the existing PlaybookPane / TranscriptPane / AdvisorPane layout) and `summary` (shows `<SummaryPane meetingId={...} />`). The `summary` tab SHALL be disabled (cannot be activated, rendered with reduced opacity / cursor-not-allowed) when `meeting.status !== "completed"`; on hover the disabled tab SHALL show a localised tooltip with text equivalent to "會議結束後可看摘要" (zh-TW) / "Summary becomes available after the meeting ends" (en).

The active tab SHALL persist across page reloads via `useDetailTab(meetingId)` hook backed by `localStorage` keyed on `meeting-detail-tab:{meetingId}`. If the persisted value is `summary` but `meeting.status !== "completed"`, the page SHALL fall back to `workspace` (avoid landing on a disabled tab).

The `<SummaryPane>` component SHALL only mount when the `summary` tab is the active tab (avoid wasted GET / React Query fetches when the user is on Workspace).

#### Scenario: Tabs render with workspace active by default for a fresh visit

- **GIVEN** a navigation to `/meetings/{id}` for a meeting whose `localStorage` has no persisted tab
- **WHEN** the detail page mounts
- **THEN** the page SHALL render two tab triggers (`workspace`, `summary`) AND the `workspace` tab content (3-column layout) SHALL be visible AND `<SummaryPane>` SHALL NOT be in the DOM

#### Scenario: Summary tab is disabled when meeting status is not completed

- **GIVEN** a meeting with `status = "in_progress"`
- **WHEN** the detail page mounts
- **THEN** the `summary` tab trigger SHALL have its `disabled` attribute set; clicking it SHALL NOT switch the active tab

#### Scenario: Summary tab is enabled when meeting status is completed

- **GIVEN** a meeting with `status = "completed"`
- **WHEN** the detail page mounts AND the user clicks the `summary` tab trigger
- **THEN** the active tab SHALL switch to `summary` AND `<SummaryPane>` SHALL render in the DOM AND the `localStorage` key `meeting-detail-tab:{meetingId}` SHALL update to `summary`

#### Scenario: Persisted summary tab on a non-completed meeting falls back to workspace

- **GIVEN** `localStorage` has `meeting-detail-tab:m_x` = `summary` AND meeting `m_x` has `status = "scheduled"`
- **WHEN** the detail page mounts
- **THEN** the active tab SHALL be `workspace` (not the persisted `summary` value, because the meeting is not yet completed)


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: SummaryPane renders 3 states (loading, pending, done) with regenerate and export controls

The web UI SHALL provide a `SummaryPane(meetingId)` component that fetches summary state via React Query (`summaryQueryOptions(meetingId)`). The component SHALL render exactly one of three visual states based on the response:

(1) **React Query is loading** (initial fetch in flight): render a skeleton placeholder with `data-testid="summary-loading"`.

(2) **Response shape is pending** (200 + `{status: "pending"}`): render a skeleton plus a localised hint "生成中⋯（約 30-60 秒）" / "Generating… (about 30-60 seconds)" with `data-testid="summary-pending"`. The hook SHALL poll the GET endpoint every 1 second while in this state until the response transitions to a Summary or 404.

(3a) **Response shape is Summary AND `is_stale === false`**: render a status row at top showing localised "生成於 {timestamp}" / "Generated {timestamp}", a `重新生成` / `Regenerate` button (calls POST), and an `匯出 .md` / `Export .md` button (calls `exportSummaryAsMarkdown`); render the markdown body via `<MarkdownPreview source={summary.markdown} />`.

(3b) **Response shape is Summary AND `is_stale === true`**: same as 3a, plus an `<Alert>` immediately above the markdown body with localised text "⚠ 內容已更新，建議重新生成" / "⚠ Content has been updated; consider regenerating" with `data-testid="summary-stale-alert"`.

(4) **Response is 404 `summary.not_found`**: render an empty-state with localised "尚無摘要" / "No summary yet" plus a `生成摘要` / `Generate summary` button (calls POST). `data-testid="summary-empty"`.

(5) **POST returns 409 `summary.busy`**: button click SHALL display a toast / inline message "上一個生成尚未完成" / "Previous generation still running"; the button SHALL re-disable until the next GET poll resolves.

#### Scenario: Summary tab on a completed meeting with no row renders empty state with Generate button

- **GIVEN** the GET returns 404 `summary.not_found` AND no in-flight task
- **WHEN** SummaryPane renders
- **THEN** the pane SHALL render `data-testid="summary-empty"` AND a button labelled `生成摘要` (zh-TW) / `Generate summary` (en) SHALL be visible

#### Scenario: Pending state polls until done

- **GIVEN** the first GET returns 200 `{status: "pending"}`
- **WHEN** SummaryPane renders
- **THEN** the pane SHALL render `data-testid="summary-pending"` with a "生成中⋯" hint AND the React Query hook SHALL refetch every 1 second AND when a subsequent GET returns 200 with a Summary, the pane SHALL re-render to the done state

#### Scenario: Stale alert visible when is_stale is true

- **GIVEN** the GET returns a Summary with `is_stale: true`
- **WHEN** SummaryPane renders
- **THEN** the pane SHALL render the markdown body AND `data-testid="summary-stale-alert"` SHALL be visible immediately above the body

#### Scenario: Regenerate click POSTs and transitions UI to pending

- **GIVEN** a SummaryPane in the done state
- **WHEN** the user clicks the `重新生成` / `Regenerate` button
- **THEN** the hook SHALL call `POST /api/meetings/{id}/summary` AND on the 202 response SHALL invalidate the React Query cache so the next GET picks up the new pending state

#### Scenario: Export click writes markdown to user-chosen file (or downloads as fallback)

- **GIVEN** a SummaryPane in the done state with markdown content "## 重點討論\n- foo"
- **WHEN** the user clicks the `匯出 .md` / `Export .md` button
- **THEN** the helper `exportSummaryAsMarkdown(meeting, markdown)` SHALL be invoked; the suggested filename SHALL be `{meeting.title}-{YYYY-MM-DD}.md` with non-filesystem-safe characters replaced by `_`; on browsers supporting File System Access API the native save dialog SHALL open; on others a blob download SHALL fire

<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: Detail page metadata card exposes ASR provider selector, recording badge, and re-run action

The meeting detail page's metadata card (the existing area showing 對方 / 我方 / 狀態 / ASR 引擎 / 建立時間) SHALL gain three new UI elements integrated INLINE with the existing rows (NOT in a separate card):

(1) **AsrProviderSelector** — replaces the existing read-only "ASR 引擎" label with a dropdown (`<select>` or shadcn equivalent) of two options: "Whisper" and "Qwen3", driven by `meeting.asr_provider`. Switching the dropdown SHALL fire a PUT mutation to `/api/meetings/{id}` with `{asr_provider: <new value>}` and SHALL display a localised hint underneath: "切換下一場會議生效" / "Takes effect on the next meeting" so the user understands the change is not retroactive to in-flight work.

(2) **RecordingBadge** — a new row labelled "錄音" / "Recording" with a coloured-dot indicator and text: green dot + "錄音可用" / "Recording available" when `meeting.recordings_available === true`; grey dot + "錄音已過期" / "Recording expired" when `false`. NO emoji per project UI standards (`feedback_ui_standards_no_emoji_magicui`); use a Tailwind background-colour `<span>` for the dot.

(3) **RerunButton** — a new action row (visually separated by a thin divider from the metadata) containing a button labelled "重新轉錄" / "Re-run transcription". The button SHALL be rendered ONLY when `meeting.status === "completed"` AND `meeting.recordings_available === true` AND `meeting.rerun_asr_pending === false`. Clicking SHALL call POST `/api/meetings/{id}/rerun_asr`; on 202 the button enters a loading state until the next React Query GET sees `rerun_asr_pending === true`, after which it disappears (replaced by the in-flight overlay in the transcript pane).

#### Scenario: AsrProviderSelector renders dropdown reflecting current meeting.asr_provider

- **GIVEN** a meeting with `asr_provider = "qwen3"`
- **WHEN** the detail page renders
- **THEN** the dropdown SHALL show "Qwen3" as the selected option AND the "切換下一場會議生效" hint SHALL be visible below

#### Scenario: Switching the dropdown PUTs the new value and shows confirmation hint

- **GIVEN** a dropdown currently showing "Qwen3"
- **WHEN** the user selects "Whisper" from the dropdown
- **THEN** a PUT request SHALL fire to `/api/meetings/{id}` with body containing `asr_provider: "whisper"`; on 200 the dropdown SHALL reflect the new selection AND the hint text SHALL remain visible

#### Scenario: RecordingBadge shows available state with green dot

- **GIVEN** a meeting with `recordings_available = true`
- **WHEN** the detail page renders
- **THEN** the recording row SHALL render an element with `data-testid="recording-badge"` AND `data-state="available"` AND text containing the localised "錄音可用" / "Recording available"

#### Scenario: RecordingBadge shows expired state with grey dot

- **GIVEN** a meeting with `recordings_available = false`
- **WHEN** the detail page renders
- **THEN** `data-testid="recording-badge"` SHALL be present with `data-state="expired"` AND localised text "錄音已過期" / "Recording expired"

#### Scenario: RerunButton hidden when meeting is in_progress

- **GIVEN** a meeting with `status = "in_progress"`
- **WHEN** the detail page renders
- **THEN** `data-testid="rerun-button"` SHALL NOT be in the DOM

#### Scenario: RerunButton hidden when recordings expired

- **GIVEN** a meeting with `status = "completed"` AND `recordings_available = false`
- **WHEN** the detail page renders
- **THEN** `data-testid="rerun-button"` SHALL NOT be in the DOM

#### Scenario: RerunButton click POSTs and enters loading state

- **GIVEN** a completed meeting with available recordings and a visible RerunButton
- **WHEN** the user clicks the button
- **THEN** a POST `/api/meetings/{id}/rerun_asr` SHALL fire; on 202 response the button SHALL show a transient loading state until the next meeting GET refetch indicates `rerun_asr_pending === true`, at which point the button SHALL disappear


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: TranscriptPane shows progress overlay while re-run is pending

The web UI's existing TranscriptPane SHALL render a skeleton + progress overlay when EITHER `meeting.rerun_asr_pending === true` (per the meeting GET response) OR the React Query `useRerunStatus(meetingId)` hook reports `status: "pending"`. The overlay SHALL display a localised "重新轉錄中..." / "Re-running transcription..." line plus a chunk counter "({chunks_processed}/{chunks_total} chunks)" pulled from the polled status response. The chunk counter SHALL display "(...)" while `chunks_total === 0` (initial moment before the task estimates the total).

When the polling sees `status: "idle"` after a transition from `"pending"`, the hook SHALL invalidate the React Query cache key `["transcripts", meetingId]` so the TranscriptPane fetches fresh chunks; the overlay SHALL disappear; the existing transcript rendering SHALL show the new content.

#### Scenario: Overlay visible during pending re-run with progress text

- **GIVEN** a completed meeting with `rerun_asr_pending = true` AND a polled status of `{status: "pending", chunks_processed: 12, chunks_total: 45}`
- **WHEN** TranscriptPane renders
- **THEN** an element with `data-testid="transcript-rerun-overlay"` SHALL be visible containing the localised "重新轉錄中" text AND the substring "(12/45 chunks)"

#### Scenario: Overlay hidden when re-run completes; new content rendered

- **GIVEN** TranscriptPane previously showed the overlay
- **WHEN** the polled status transitions from `pending` to `idle`
- **THEN** the React Query cache key `["transcripts", meetingId]` SHALL be invalidated; TranscriptPane SHALL re-render with `data-testid="transcript-rerun-overlay"` absent AND new transcript chunks visible (assuming the GET returned the new rows)

<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->