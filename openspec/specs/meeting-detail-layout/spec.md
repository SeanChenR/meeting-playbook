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

The meeting detail page SHALL wrap its main content inside a Tabs primitive with two tabs: `workspace` (default active, renders the three-column `<Workspace>`) and `summary` (renders the new two-column `<MeetingDetailSummaryView>`). The `summary` tab SHALL be disabled (cannot be activated, rendered with reduced opacity / cursor-not-allowed) when `meeting.status !== "completed"`; on hover the disabled tab SHALL show a localised tooltip with text equivalent to "會議結束後可看摘要" (zh-TW) / "Summary becomes available after the meeting ends" (en).

The active tab SHALL persist across page reloads via `useDetailTab(meetingId)` hook backed by `localStorage` keyed on `meeting-detail-tab:{meetingId}`. If the persisted value is `summary` but `meeting.status !== "completed"`, the page SHALL fall back to `workspace` (avoid landing on a disabled tab).

The `<MeetingDetailSummaryView>` component SHALL only mount when the `summary` tab is the active tab (avoid wasted GET / React Query fetches when the user is on Workspace).

#### Scenario: Tabs render with workspace active by default for a fresh visit

- **GIVEN** a navigation to `/meetings/{id}` for a meeting whose `localStorage` has no persisted tab
- **WHEN** the detail page mounts
- **THEN** the page SHALL render two tab triggers (`workspace`, `summary`) AND the `workspace` tab content (three-column workspace) SHALL be visible AND `<MeetingDetailSummaryView>` SHALL NOT be in the DOM

#### Scenario: Summary tab is disabled when meeting status is not completed

- **GIVEN** a meeting with `status = "in_progress"`
- **WHEN** the detail page mounts
- **THEN** the `summary` tab trigger SHALL have its `disabled` attribute set; clicking it SHALL NOT switch the active tab

#### Scenario: Summary tab renders two-column view when active and meeting is completed

- **GIVEN** a meeting with `status = "completed"`
- **WHEN** the user activates the `summary` tab
- **THEN** `<MeetingDetailSummaryView>` SHALL mount inside the tab panel with `data-testid="meeting-summary-view"` AND it SHALL render two columns: left containing `<SummaryPane>` and right containing the AI chat placeholder (`data-testid="meeting-summary-chat-slot"`)


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
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

---
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


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
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

<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: Meeting detail page SHALL render a prev/next navigation group alongside the BackLink

The meeting detail page SHALL render a single thin row at the top of the page content (above `MeetingHeaderBar`) containing **three groups** separated by a vertical divider:

1. **Back-to-list link** (leftmost) — Lucide `ArrowLeft` icon (14px, `stroke-width: 1.5`) + i18n label `meetings.detail.backToList` (zh-TW: `會議列表` / en: `All meetings`). Wrapped in TanStack `<Link to="/meetings">`.
2. **Vertical divider** — `w-px h-3 bg-(--color-border)` (visual separator between parent navigation and lateral navigation).
3. **`<MeetingPrevNextNav>` group** (rightmost) — `[ChevronLeft]` + previous-meeting title (when present), a `/` separator, and next-meeting title (when present) + `[ChevronRight]`. The order in the database SHALL be by `created_at` descending (newest first); "previous" is the meeting created right before the current one.

The icons SHALL use distinct visual weight to communicate navigation direction: `ArrowLeft` (thicker) for parent navigation versus `ChevronLeft / ChevronRight` (thinner) for lateral navigation between siblings.

The previous standalone BackLink-to-list element from before this change is replaced by the back link on this row; there SHALL NOT be a separate BackLink row above this one. The global navigation in `ProtectedShell` header still exists as a secondary entry point but the detail-page back link is the primary affordance.

#### Scenario: Row renders three groups with back link, divider, and prev/next nav

- **GIVEN** a meeting `m_2` created after `m_1` and before `m_3` (newest-first ordering)
- **WHEN** the user opens `/meetings/m_2`
- **THEN** the top nav row SHALL contain a back-to-list link with text `會議列表` (zh-TW) AND a vertical divider element AND a prev/next group showing previous meeting title `Q3 review` (m_1) on the left and next meeting title `客戶X kickoff` (m_3) on the right

#### Scenario: Back-to-list link navigates to /meetings

- **GIVEN** the user is on `/meetings/m_2`
- **WHEN** the user clicks the back-to-list link with text `會議列表`
- **THEN** the router SHALL navigate to `/meetings`

#### Scenario: Back link uses ArrowLeft icon; prev/next use ChevronLeft/Right

- **GIVEN** the top nav row is visible
- **WHEN** the icons within it are inspected
- **THEN** the back-to-list link SHALL contain an `<svg>` matching Lucide `ArrowLeft` AND the prev meeting link SHALL contain an `<svg>` matching Lucide `ChevronLeft` AND the next meeting link SHALL contain an `<svg>` matching Lucide `ChevronRight`

#### Scenario: Prev/next nav and back link occupy a single thin row above MeetingHeaderBar

- **GIVEN** the page is rendered with both back link and prev/next available
- **WHEN** the DOM is inspected
- **THEN** the back link, divider, and prev/next group SHALL all sit inside the same parent element (single horizontal row) AND that row SHALL appear in document order before the `MeetingHeaderBar` element


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Meeting detail page renders MeetingAudioMiniPlayer pinned to the bottom

The meeting detail page (`packages/web/src/routes/meetings/detail.tsx`) SHALL render `<MeetingAudioMiniPlayer>` (defined in the `audio-playback` capability) as a persistent sticky bar at the bottom of the page in BOTH `columns` mode and `stack` mode. The mini-player SHALL NOT be placed inside any of the three panes (Playbook / Transcript / Advisor); it SHALL live in the page-level layout container below them. The mini-player SHALL remain visible regardless of which Tab is active when the Tabs UI is enabled (per the existing "Detail page wraps existing workspace in a Tabs UI" requirement). When no chunk has been selected for playback, the mini-player SHALL render in an idle state with the Play / Pause button disabled and the chunk-navigation buttons disabled; the Speed dropdown SHALL remain enabled so the user can pre-set their preferred speed before pressing ▶ on a chunk.

The mini-player's presence SHALL NOT alter the 30/40/30 grid widths defined in the columns-mode requirement, nor the P-T-A vertical ordering defined in the stack-mode requirement. The mini-player's height SHALL be reserved in the page layout so the bottom-most content of the active pane is NOT occluded by the mini-player bar.

#### Scenario: Mini-player renders in columns mode at the page bottom

- **GIVEN** a meeting detail page in columns mode with a viewport wider than 1024px
- **WHEN** the page renders
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL be present in the DOM below the three pane columns; its container SHALL have CSS `position: sticky; bottom: 0`; the three pane columns above SHALL retain the 30/40/30 widths

#### Scenario: Mini-player renders in stack mode below the three stacked panes

- **GIVEN** a meeting detail page in stack mode
- **WHEN** the page renders
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL be the last element in the page layout; the Playbook → Transcript → Advisor vertical order above it SHALL be unchanged

#### Scenario: Mini-player stays visible across Tab switches

- **GIVEN** a meeting detail page using the Tabs UI with Workspace tab currently active
- **WHEN** the user switches to the Summary tab
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL still be visible in the DOM at the page bottom; if a chunk was playing the playback SHALL continue uninterrupted

#### Scenario: Idle mini-player has disabled play and navigation buttons

- **GIVEN** a freshly loaded meeting detail page where the user has NOT clicked ▶ on any chunk
- **WHEN** the page renders
- **THEN** the mini-player's Play/Pause button SHALL have the `disabled` attribute; the Previous and Next chunk buttons SHALL be disabled; the Speed dropdown SHALL be enabled and SHALL show the user's persisted `localStorage.miniPlayerRate` value (defaulting to `1.0x`)

<!-- @trace
source: slice-16-transcript-edit-and-playback
updated: 2026-05-15
code:
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/speaker/finalize.py
  - bun.lock
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/calendar/router.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - .env.example
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/ui/dialog.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
tests:
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/audio_playback/__init__.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
-->

---
### Requirement: MetadataCard header renders a related-meetings section between prev/next nav and metadata columns

The `/meetings/$id` route SHALL render a `<MeetingLinksSection>` element
inside the MetadataCard header, positioned after the prev/next navigation
group and before the two metadata columns. The section SHALL display:

- A heading using the `meetings.links.heading` i18n key.
- A count derived from `meetings.links.count_one` / `meetings.links.count_other`
  plural keys.
- A list of links each rendered as a navigation link to `/meetings/{other_meeting_id}`
  that displays `other_meeting_title` and `other_meeting_scheduled_start_at`.
- A delete button (trash icon from `animate-ui` or a static lucide icon) on
  each list row that triggers `DELETE /api/meetings/{currentMeetingId}/links/{link_id}`.
- A `+ 關聯` / `+ Link` button (using the `meetings.links.addButton` i18n
  key) that opens the `<MeetingLinkPicker>` modal.

When the meeting has zero links, the section SHALL render the
`meetings.links.empty` empty state and SHALL still render the
`+ 關聯` / `+ Link` button. When the meeting has more than ten links, the
list SHALL render in a collapsed state showing the first ten with a
toggle button that uses the `meetings.links.showMore` /
`meetings.links.showFewer` i18n keys.

The existing prev/next navigation, BackLink, MetadataCard two-column layout,
recording badge, ASR provider selector, and CaptureIndicator behavior SHALL
remain unchanged.

#### Scenario: Empty state renders heading, empty hint, and add button

- **GIVEN** the user navigates to `/meetings/A` and meeting A has zero
  related links
- **WHEN** the MetadataCard header renders
- **THEN** the page SHALL render an element with `data-testid="meeting-links-section"`
- **AND** that element SHALL contain the `meetings.links.heading` text
- **AND** it SHALL contain the `meetings.links.empty` empty-state text
- **AND** it SHALL contain a button with the `meetings.links.addButton` label

#### Scenario: Linked meetings render as navigation links with delete affordance

- **GIVEN** meeting A has two related links to meetings B and C
- **WHEN** the MetadataCard header renders
- **THEN** the meeting-links-section SHALL render a list of two items
- **AND** each item SHALL be an anchor with `href="/meetings/{B-id}"` and
  `href="/meetings/{C-id}"` respectively, showing the other meeting's title
- **AND** each item SHALL render a delete button with
  `data-testid="meeting-link-delete-{link_id}"`

#### Scenario: Collapse triggers when link count exceeds ten

- **GIVEN** meeting A has fifteen related links
- **WHEN** the MetadataCard header renders
- **THEN** the meeting-links-section SHALL render exactly ten link items by
  default
- **AND** a toggle button with the `meetings.links.showMore` label SHALL be
  present
- **AND** clicking the toggle SHALL reveal the remaining five links and
  switch the toggle label to `meetings.links.showFewer`

#### Scenario: Add button opens the MeetingLinkPicker modal

- **GIVEN** the user is on `/meetings/A`
- **WHEN** the user clicks the button labeled `meetings.links.addButton`
- **THEN** a modal element with `data-testid="meeting-link-picker"` SHALL
  open
- **AND** the modal SHALL contain a typeahead input using the
  `meetings.links.picker.placeholder` label

#### Scenario: Successful link creation refreshes the section

- **GIVEN** the user has opened the picker on `/meetings/A` and selected
  meeting B
- **WHEN** the user confirms the selection and the
  `POST /api/meetings/A/links` call returns HTTP 201
- **THEN** the picker modal SHALL close
- **AND** the meeting-links-section SHALL re-render including meeting B in
  the list

#### Scenario: Duplicate link rejection keeps modal open and shows localized error

- **GIVEN** the user has opened the picker on `/meetings/A` and selected
  meeting B
- **AND** meeting A and meeting B are already linked
- **WHEN** the user confirms the selection and the server responds with
  HTTP 409 and `error_code = "meeting_link.duplicate"`
- **THEN** the picker modal SHALL remain open
- **AND** the picker SHALL display the message bound to
  `errors.meeting_link.duplicate` from the active locale

#### Scenario: Delete icon removes the link inline

- **GIVEN** meeting A has a related link to meeting B with link id L
- **WHEN** the user clicks the element with
  `data-testid="meeting-link-delete-L"` and the server responds with HTTP 204
- **THEN** the meeting-links-section SHALL re-render without the row for L
- **AND** the section SHALL fall back to the empty state if L was the only
  link

<!-- @trace
source: slice-21-meeting-linking
updated: 2026-05-17
code:
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/uv.lock
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - bun.lock
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/meetings/models.py
  - README.md
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - CONTEXT.md
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/public/icons/qwen.png
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/public/icons/whisper.png
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/components/settings/layout.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - .env.example
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/web/src/lib/calendar-api.ts
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/components/ui/dialog.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/index.css
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/stats-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/DashboardPage.tsx
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/lib/tags-api.ts
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
tests:
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/web/src/App.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/lib/meeting-links-api.test.ts
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/backend/tests/conftest.py
  - packages/backend/tests/calendar/test_get_event_endpoint.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/backend/tests/attachments/__init__.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/tags/__init__.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/meeting_links/test_router.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/tags/test_models.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/backend/tests/audio_playback/__init__.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/transcript_edit/test_router.py
-->

---
### Requirement: Workspace SHALL always render the three columns side-by-side with equal width

The `<Workspace>` component SHALL always render three columns in horizontal grid order: Playbook → Transcript → Advisor. The grid SHALL use `1fr 1fr 1fr` (equal width); 30/40/30 weighting is replaced. Each column SHALL have a minimum width of `340px` and a maximum width of `460px`. The entire workspace block SHALL be centered with `max-w-[1380px] mx-auto`. The `<Workspace>` props SHALL no longer accept a `layout` parameter.

#### Scenario: Workspace renders three equal-width columns

- **GIVEN** detail page workspace tab active on a 1440-wide viewport
- **WHEN** the page renders
- **THEN** three column wrappers (`data-testid="meeting-column-playbook|transcript|advisor"`) SHALL be present in that document source order AND each SHALL compute approximately one-third of the available workspace width (within ±20px tolerance for gaps)

#### Scenario: Workspace block is centered with a 1380px max-width

- **GIVEN** detail page workspace tab on a 1920-wide viewport
- **WHEN** the page renders
- **THEN** the outer workspace container SHALL have a computed `max-width` of `1380px` AND SHALL be horizontally centered (left + right margins approximately equal)


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Each workspace column SHALL render its own header with a localised title and column-specific tools

Each of the three workspace columns SHALL render a sticky header at its top containing a localised column title and an optional tools slot for column-specific actions. The header SHALL remain visible when the column body scrolls underneath. The header SHALL be sourced from i18n keys:
- Playbook column: `meetings.detail.columnPlaybook` (zh-TW: `劇本`, en: `Playbook`).
- Transcript column: `meetings.detail.columnTranscript` (zh-TW: `逐字稿`, en: `Transcript`).
- Advisor column: `meetings.detail.columnAdvisor` (zh-TW: `戰術建議`, en: `Advisor`).

#### Scenario: Column headers display correct localised titles

- **GIVEN** detail page workspace tab in zh-TW locale
- **WHEN** the page renders
- **THEN** the playbook column header SHALL display the text `劇本` AND the transcript column header SHALL display `逐字稿` AND the advisor column header SHALL display `戰術建議`

#### Scenario: Column header stays sticky while body scrolls

- **GIVEN** the transcript column has more chunks than fit in its viewport
- **WHEN** the user scrolls the transcript column body downward
- **THEN** the transcript column header (`逐字稿`) SHALL remain visible at the top of that column AND the column body SHALL scroll independently of the other two columns


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: The three workspace columns SHALL share an identical computed height with independent scrolling

The three workspace columns SHALL render at IDENTICAL visible height so the row presents as a balanced grid rather than a jagged silhouette. The shared height SHALL be derived from the available viewport height minus the page top stack (prev/next nav + MeetingHeaderBar + conditional alerts + tabs) and the bottom MeetingAudioMiniPlayer height (target: approximately `calc(100vh - 280px)` give-or-take a few pixels; exact value SHALL be derived at runtime via measured CSS variables). Content overflow within any column SHALL be confined to that column's own scroll container so a long transcript does not push other columns downward.

#### Scenario: Columns are visually balanced with independent scrolls

- **GIVEN** detail page workspace tab on a 1440-wide viewport with a tall transcript and a short playbook
- **WHEN** the page renders
- **THEN** the three column wrappers SHALL have equal computed heights (within 1px tolerance) AND each column's internal scroll container SHALL be independent (scrolling one does not move the others)


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: MeetingHeaderBar SHALL render core metadata as a single horizontal row

A new `MeetingHeaderBar` component SHALL replace the removed MetadataCard. It SHALL render a compact horizontal block (NOT a multi-row card) above the tabs row, containing:

(1) **First row** — meeting title (h1, 2xl bold), status badge with coloured dot, scheduled-time window text ("HH:mm – HH:mm" format), 對方 + 我方 display names with avatars, and (when `phase` is `in_progress` or `ending`) the inline `CaptureIndicator`. A recording-availability indicator (green dot "錄音可用" / grey dot "錄音已過期" / hidden if `recordings_available` is absent) SHALL appear on the same row in compact form.

(2) **Second row** — primary action buttons that vary by status/bucket, followed by the `MeetingOverflowMenu` trigger rendered with the `MoreHorizontal` Lucide icon. Primary actions, each rendered with its Lucide icon to the left of the label:
- `upcoming` + `phase === "idle"`: `Play` icon + 開始 label, plus `Download` icon + 匯出 label
- `in_progress`: `Square` icon + 結束 label
- `needs_recording`: `Upload` icon + 上傳音訊 label, plus `Download` icon + 匯出 label
- `completed`: `Download` icon + 匯出 label

All icons SHALL be imported from `lucide-react`. Buttons MUST NOT use unicode emoji glyphs in labels or as visual affordances.

The header bar SHALL emit `data-testid="meeting-header-bar"`. The previous `data-testid="meeting-metadata-card"` selector SHALL NOT appear on the page.

#### Scenario: Header bar shows title, status, scheduled time, and primary action

- **GIVEN** a meeting with `status = "scheduled"`, `title = "Q4 進攻會議"`, `scheduled_start_at = 2026-06-15T14:30:00Z`, `scheduled_end_at = 2026-06-15T15:30:00Z`
- **WHEN** the detail page mounts in zh-TW locale
- **THEN** `data-testid="meeting-header-bar"` SHALL be present AND its text content SHALL contain `Q4 進攻會議` AND `06/15` AND `14:30` AND `15:30` AND a "scheduled" status badge AND a 開始 button rendered with the `Play` Lucide icon AND a 匯出 button rendered with the `Download` Lucide icon

#### Scenario: MetadataCard test selector is no longer present

- **WHEN** the detail page renders for any meeting
- **THEN** no element with `data-testid="meeting-metadata-card"` SHALL exist in the DOM


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: MeetingOverflowMenu SHALL consolidate secondary affordances behind a single ⋯ trigger

A new `MeetingOverflowMenu` component SHALL render a shadcn DropdownMenu opened by a `⋯` icon button in the right side of `MeetingHeaderBar`'s second row. The menu SHALL contain the following items in document order, grouped with two separators:

| Group | Item key | i18n key | Trigger behavior | Visibility |
|---|---|---|---|---|
| Data | `edit` | `meetings.detail.menu.edit` | Opens the existing Edit Meeting Dialog. | Always |
| Data | `tags` | `meetings.detail.menu.tags` | Opens a Dialog containing the current `<TagPicker>` and existing tag chips list. | Always |
| Data | `attachments` | `meetings.detail.menu.attachments` | Opens a Dialog containing `<AttachmentDropzone>`. Item label SHALL include attachment count badge. | Always |
| Data | `linked` | `meetings.detail.menu.linked` | Opens a Dialog containing `<MeetingLinksSection>`. Item label SHALL include linked-meeting count badge. | Always |
| (separator) | | | | |
| Settings | `mode` | `meetings.detail.menu.mode` | Opens a popover containing `<RecordingModeSelector>`. | Only when `meeting.status === "scheduled"` AND `session.phase === "idle"`; otherwise hidden (not rendered, NOT merely disabled). |
| Settings | `rerun` | `meetings.detail.menu.rerun` | Triggers existing `<RerunButton>` behavior (POST `/api/meetings/{id}/rerun_asr`). | Always (visibility internal to RerunButton's own conditions still applies — when the button would not normally render, the menu item SHALL be disabled with a tooltip). |
| (separator) | | | | |
| Destructive | `delete` | `meetings.detail.menu.delete` | Opens the existing delete confirmation AlertDialog. Item label SHALL use destructive (red) text colour. | Always |

The trigger button SHALL emit `data-testid="meeting-overflow-trigger"`. Each menu item SHALL emit `data-testid="meeting-menu-item-<key>"` where `<key>` is the item key column above (e.g., `meeting-menu-item-edit`).

**ASR Provider switching is intentionally NOT in this menu**; it is configured at `/settings/integrations` (existing route hosting `<AsrProviderSelector>`). The menu therefore contains 8 items, not 9. Any test asserting a 9-item menu is outdated.

#### Scenario: Menu shows eight items grouped by separators for an idle scheduled meeting

- **GIVEN** a meeting with `status = "scheduled"` and `session.phase = "idle"`
- **WHEN** the user clicks `data-testid="meeting-overflow-trigger"`
- **THEN** the open menu SHALL contain all eight items above (in document order: edit, tags, attachments, linked, separator, mode, rerun, separator, delete) AND the delete item label SHALL have destructive colouring AND no item with `data-testid="meeting-menu-item-asr"` SHALL be present

#### Scenario: ASR Provider switching is not exposed by the detail page menu

- **GIVEN** a meeting in any status
- **WHEN** the overflow menu is opened
- **THEN** no menu item SHALL trigger an ASR Provider switch popover or dialog AND any user wishing to change ASR Provider SHALL navigate to `/settings/integrations` instead

#### Scenario: Recording mode item is hidden once the session leaves idle

- **GIVEN** a meeting with `session.phase = "in_progress"`
- **WHEN** the user opens the overflow menu
- **THEN** the menu SHALL NOT contain `data-testid="meeting-menu-item-mode"` AND the menu SHALL still contain the other seven items

#### Scenario: Attachments item shows count badge

- **GIVEN** a meeting with three attachments
- **WHEN** the user opens the overflow menu
- **THEN** the attachments item label SHALL contain the localised attachments label AND a "3" count badge AND clicking it SHALL open a dialog with `data-testid="meeting-attachments-dialog"` containing the AttachmentDropzone


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Summary tab SHALL render a two-column layout with the markdown summary on the left and an AI-chat placeholder slot on the right

The `<MeetingDetailSummaryView>` component (mounted inside the summary tab panel when active) SHALL render a CSS grid with two equal-width columns at gap `16px`, centered with `max-w-[1380px] mx-auto`. Left column SHALL contain the existing `<SummaryPane meetingId>`. Right column SHALL render a placeholder slot for a future post-meeting AI chat feature, containing a localised header ("摘要對話" / "Summary Q&A") and a localised placeholder body ("即將推出" / "Coming soon"). The right column SHALL emit `data-testid="meeting-summary-chat-slot"`.

The right column SHALL NOT submit any network requests in this change. It is a layout slot only.

#### Scenario: Summary view renders two-column markdown + AI chat slot

- **GIVEN** a meeting with `status = "completed"` and the user activated the summary tab
- **WHEN** the page renders
- **THEN** `data-testid="meeting-summary-view"` SHALL contain exactly two direct children grid cells AND the left cell SHALL contain `<SummaryPane>` content AND the right cell SHALL contain `data-testid="meeting-summary-chat-slot"` with a localised "即將推出" (zh-TW) / "Coming soon" (en) placeholder

#### Scenario: Summary chat slot makes no network requests

- **WHEN** the summary tab is active and the AI chat slot renders
- **THEN** zero network requests SHALL be issued for any AI-chat / post-meeting Q&A endpoint


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: HeadphonesHint SHALL render as a dismissible inline alert when dual mode is selected before start

The existing `HeadphonesHint` component SHALL render as a single-line inline alert (shadcn `<Alert>` variant `info`) below the `MeetingHeaderBar` and above the tabs row when ALL of the following are true: `meeting.status === "scheduled"` AND `session.phase === "idle"` AND `session.mode === "dual"`. The alert SHALL include a dismiss icon button rendered with the `X` Lucide icon that hides the alert for the current page lifetime (no localStorage persistence — re-entering the page resets the dismissal). The previous card-style rendering is removed.

#### Scenario: HeadphonesHint appears as inline alert when dual + idle + scheduled

- **GIVEN** a scheduled meeting with `session.phase = "idle"` and the user selected `dual` recording mode
- **WHEN** the page renders
- **THEN** an element with `data-testid="headphones-hint"` SHALL be present AND it SHALL have the shadcn alert structure (NOT a Card) AND it SHALL be positioned between MeetingHeaderBar and the tabs row

#### Scenario: HeadphonesHint disappears after user dismisses for current page lifetime

- **GIVEN** the hint is visible on a scheduled meeting page
- **WHEN** the user clicks the dismiss icon button (Lucide `X`)
- **THEN** the hint SHALL disappear from the DOM AND remain absent for the rest of the current page mount AND reappear on next page navigation to the same URL


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: i18n SHALL provide Chinese "劇本" terminology for Playbook UI strings and column headers

The playbook UI heading and the three workspace column headers SHALL use the following localised text:

| i18n key | zh-TW | en |
|---|---|---|
| `playbook.heading` | `劇本` | `Playbook` |
| `meetings.detail.columnPlaybook` | `劇本` | `Playbook` |
| `meetings.detail.columnTranscript` | `逐字稿` | `Transcript` |
| `meetings.detail.columnAdvisor` | `戰術建議` | `Advisor` |
| `meetings.detail.menu.edit` | `編輯會議` | `Edit meeting` |
| `meetings.detail.menu.tags` | `管理標籤` | `Manage tags` |
| `meetings.detail.menu.attachments` | `附件` | `Attachments` |
| `meetings.detail.menu.linked` | `相關會議` | `Linked meetings` |
| `meetings.detail.menu.mode` | `錄音模式` | `Recording mode` |
| `meetings.detail.menu.rerun` | `重跑轉錄` | `Re-run transcription` |
| `meetings.detail.menu.delete` | `刪除會議` | `Delete meeting` |
| `meetings.detail.summaryChatSlotTitle` | `摘要對話` | `Summary Q&A` |
| `meetings.detail.summaryChatSlotPlaceholder` | `即將推出` | `Coming soon` |
| `meetings.detail.backToList` | `會議列表` | `All meetings` |
| `meetings.detail.uploadSuccessTitle` | `音檔處理完成` | `Audio processed` |
| `meetings.detail.uploadSuccessSubtitle` | `逐字稿已自動生成` | `Transcript generated` |
| `meetings.detail.exportSuccessTitle` | `匯出完成` | `Export complete` |
| `meetings.detail.exportSuccessSubtitle` | `ZIP 已儲存到下載資料夾` | `ZIP saved to Downloads` |
| `meetings.detail.viewTranscript` | `查看逐字稿` | `View transcript` |

Code identifiers (file names, component names, variables) SHALL keep their existing English `playbook` naming. Only user-facing string values SHALL change.

The previous `meetings.detail.menu.asr` key is rescinded together with the menu item itself (see MeetingOverflowMenu MODIFIED requirement above); it SHALL NOT be present in either locale file.

#### Scenario: Both locale files declare the same keys

- **WHEN** the locales deep-equal test runs over `zh-TW.json` and `en.json`
- **THEN** all nineteen keys listed in the table above SHALL exist in both files AND no key SHALL be present in one file but missing in the other AND `meetings.detail.menu.asr` SHALL NOT exist in either file

#### Scenario: Playbook heading renders 劇本 in zh-TW

- **GIVEN** the user is in zh-TW locale viewing the detail page workspace
- **WHEN** the playbook pane renders its heading
- **THEN** the heading text SHALL contain `劇本` AND SHALL NOT contain the previous English `Playbook` text


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: All UI affordances on the meeting detail page SHALL use Lucide icon components, not emoji glyphs

Every visible icon on `/meetings/$id` — including menu item leading icons, button leading icons, column header tool buttons, dismiss buttons, empty state visuals, and any future affordance added to the page — SHALL be rendered via a `lucide-react` icon component. Unicode emoji glyphs (including but not limited to `✏`, `🏷`, `📎`, `🔗`, `⚙`, `🔄`, `🗑`, `▶`, `■`, `⤴`, `⤓`, `×`, `📅`, `📋`) SHALL NOT appear as the source character of any visual affordance in the rendered output.

The required icon-to-affordance mapping for this change is:

| Affordance | Lucide icon |
|---|---|
| Edit | `Pencil` |
| Tags | `Tag` |
| Attachments | `Paperclip` |
| Linked meetings | `Link2` |
| ASR provider settings | `Settings2` |
| Recording mode | `Mic2` |
| Re-run transcription | `RotateCw` |
| Delete | `Trash2` |
| Play / Start meeting | `Play` |
| Stop / End meeting | `Square` |
| Upload audio | `Upload` |
| Download / Export | `Download` |
| Dismiss / Close | `X` |
| Overflow menu trigger | `MoreHorizontal` |
| Expand / Collapse | `ChevronDown` / `ChevronRight` |
| Prev / Next meeting | `ChevronLeft` / `ChevronRight` |
| Summary chat placeholder visual | `MessageSquare` |
| Volume | `Volume2` |
| Advisor chat send | `SendHorizontal` |
| Advisor clear chat | `Eraser` |

Default rendered size is 16px, `stroke-width: 1.5`, `currentColor`.

This requirement applies to source code authored as part of this change; pre-existing emoji in other routes (outside `/meetings/$id`) remain governed by the future UI-overhaul change. Source comments and Spectra artifacts (proposal.md, design.md, tasks.md, spec.md) MAY reference emoji glyphs only to document what is being replaced or rejected; the rendered HTML SHALL contain none.

#### Scenario: Rendered detail page contains no emoji code points

- **GIVEN** the user loads `/meetings/$id` for any meeting status
- **WHEN** the page renders any state (loading, scheduled, in_progress, completed, needs_recording, error, plus overflow menu opened, plus headphones hint visible, plus any dialog opened)
- **THEN** the resulting DOM's text content SHALL contain zero Unicode code points in the emoji ranges U+1F300–U+1FAFF, U+2600–U+27BF, U+2700–U+27BF

#### Scenario: Every menu item renders its specified Lucide icon

- **GIVEN** the user opens the overflow menu on a scheduled idle meeting
- **WHEN** the menu is open
- **THEN** each of the nine menu items SHALL render an `<svg>` element imported from `lucide-react` matching the icon-to-affordance mapping above (e.g., the edit item renders the `Pencil` SVG, the delete item renders the `Trash2` SVG)

#### Scenario: HeadphonesHint dismiss button is a Lucide X icon

- **GIVEN** the HeadphonesHint inline alert is visible
- **WHEN** the dismiss button renders
- **THEN** it SHALL contain an `<svg>` element imported from `lucide-react`'s `X` component AND SHALL NOT contain the character `×` (U+00D7) or `✕` (U+2715) as a text node


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Summary chat slot SHALL render three static example prompt chips beneath the placeholder

The right column of `<MeetingDetailSummaryView>` (the "摘要對話" placeholder) SHALL render exactly three example prompt chips below the "即將推出" placeholder text. The chips SHALL be purely visual — non-interactive `<span>` elements with `cursor: default`, no `onClick` handler, no keyboard focus target. The chip text SHALL be hardcoded (not driven by i18n keys this change) using these zh-TW strings:

1. `「Joyce 那項做完了嗎？」`
2. `「對方資安要求摘要」`
3. `「下次該準備什麼？」`

Visual treatment: `bg-(--color-surface-2)` background, `text-(--color-muted-foreground)` text, `rounded-full`, `px-3 py-1`, `text-xs`. The three chips render in a row with `gap-2`; on narrow widths they MAY wrap.

#### Scenario: Three example chips render beneath the placeholder

- **GIVEN** a meeting with `status = "completed"` and the user activated the summary tab
- **WHEN** the right column renders
- **THEN** exactly three chip elements SHALL be present below the "即將推出" text AND each SHALL contain one of the three hardcoded strings AND each SHALL have `cursor: default` (no pointer cursor) AND none SHALL have an `onClick` handler


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: HeadphonesHint SHALL display the full localised copy explaining echo risk in dual ASR mode

The HeadphonesHint inline alert text SHALL use the following localised copy:

| Locale | Copy |
|---|---|
| zh-TW | `建議戴耳機避免回音 — 雙路 ASR 模式下，喇叭外放會被麥克風重複擷取。` |
| en | `Recommended: wear headphones to avoid echo — in dual ASR mode, speaker output will be re-captured by the microphone.` |

When the copy would otherwise truncate (viewport too narrow), the alert text SHALL wrap to a second line rather than truncate. The alert SHALL maintain its single horizontal-line layout for icon + text + dismiss button at typical 1440px viewport.

#### Scenario: Full copy is rendered, not truncated

- **GIVEN** the HeadphonesHint is visible at 1440px viewport in zh-TW
- **WHEN** the alert text renders
- **THEN** the text content SHALL contain the full string `建議戴耳機避免回音 — 雙路 ASR 模式下，喇叭外放會被麥克風重複擷取。` AND SHALL NOT end with `...` or any truncation indicator


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Overflow menu items for ASR provider and Recording mode SHALL display the current value as a sub-hint

The `mode` item in `<MeetingOverflowMenu>` SHALL render a sub-hint span to the right of the item label (between label and any trailing chevron). The sub-hint SHALL be the human-readable name of the current `session.mode` (e.g., `雙路 ASR` for zh-TW dual / `Dual ASR` for en, `單路（合流）` / `Single (merged)`).

The sub-hint visual: `text-xs text-(--color-muted-foreground)`, 8px gap from label. When the current value is unknown (e.g., loading / undefined), the sub-hint SHALL NOT render and the menu item SHALL only show its primary label.

`<MeetingOverflowMenu>` props SHALL include `modeCurrentLabel?: string`; `detail.tsx` SHALL compute this by mapping `session.mode` to the locale-correct display name before passing it in.

The ASR provider previously had a parallel sub-hint requirement; that requirement is rescinded together with the removal of the ASR menu item (see "MeetingOverflowMenu SHALL consolidate secondary affordances" requirement above). `asrCurrentLabel` SHALL NOT appear as a `<MeetingOverflowMenu>` prop.

#### Scenario: Recording mode item shows current mode name when scheduled+idle

- **GIVEN** a meeting with `status = "scheduled"`, `session.phase = "idle"`, and `session.mode = "dual"`
- **WHEN** the user opens the overflow menu
- **THEN** the mode item SHALL be visible AND its sub-hint SHALL show `雙路 ASR` (zh-TW)

#### Scenario: Mode sub-hint absent when current value is undefined

- **GIVEN** a meeting whose `session.mode` is `undefined`
- **WHEN** the user opens the overflow menu
- **THEN** the mode item (if visible per its own visibility condition) SHALL render only its primary label AND no sub-hint element SHALL be present in the item

#### Scenario: ASR menu item is absent altogether

- **WHEN** the overflow menu is opened in any meeting state
- **THEN** no element with `data-testid="meeting-menu-item-asr"` SHALL exist AND `<MeetingOverflowMenu>` SHALL NOT receive an `asrCurrentLabel` prop


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: TranscriptPane SHALL render a flag chip and highlight row when a chunk's flag_reason field is non-empty

`<TranscriptPane>` SHALL accept transcript chunk objects with an optional `flag_reason?: string` field (frontend-only type augmentation; backend MAY or MAY NOT populate this field). When a chunk's `flag_reason` is a non-empty string, the chunk row SHALL:

1. Receive an `is-flag` CSS class that applies a 4px destructive-coloured left border and a faint destructive-tinted background (`bg-(--color-destructive)/4`).
2. Render an additional small chip in the chunk's meta line (between timestamp and the chunk text), with `bg-(--color-destructive)/12` background, `text-(--color-destructive)` text, `text-xs`, `rounded-full`, `px-2 py-0.5`, displaying the `flag_reason` string verbatim (e.g., `反對訊號`).

When `flag_reason` is `undefined`, `null`, or an empty string, the chunk SHALL render with no highlight and no chip — visually identical to before this change. The frontend SHALL NOT attempt to derive `flag_reason` itself; it is purely a passthrough of whatever the backend or test fixture provides.

#### Scenario: Chunk with flag_reason is highlighted with a destructive chip

- **GIVEN** the transcript pane receives a chunk with `flag_reason = "反對訊號"`
- **WHEN** the pane renders
- **THEN** that chunk's row SHALL have the `is-flag` class AND the meta line SHALL contain a chip element with the destructive-coloured visual treatment and the text `反對訊號`

#### Scenario: Chunks without flag_reason render normally

- **GIVEN** the transcript pane receives ten chunks where none have `flag_reason` set
- **WHEN** the pane renders
- **THEN** zero chunks SHALL have the `is-flag` class AND zero chip elements with destructive colouring SHALL appear in the meta lines


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: AdvisorPane SHALL render reply chips on AI bubbles whose suggestion_text is provided, wiring the apply chip to fill the advisor input

`<AdvisorPane>` SHALL accept advisor message objects (AI bubbles) with an optional `suggestion_text?: string` field (frontend-only type augmentation). When an AI bubble has a non-empty `suggestion_text`, the bubble body SHALL include a chip row directly beneath the message content containing exactly two chips:

1. `[套用為回覆]` (zh-TW) / `[Use as reply]` (en) — interactive button-style chip. Clicking it SHALL invoke the new `onApplySuggestion(suggestion_text: string)` prop on `<AdvisorPane>`. The advisor input controller SHALL update its current value to the `suggestion_text` immediately. No network request SHALL fire.
2. `[換一個說法]` (zh-TW) / `[Rephrase]` (en) — disabled. Visually rendered with `opacity-50` and `cursor-not-allowed`. The element SHALL carry a `title` attribute (tooltip) with localised text equivalent to "下版本上線" (zh-TW) / "Coming next release" (en). Clicking it SHALL be a no-op.

When `suggestion_text` is `undefined`, `null`, or empty string, no chip row SHALL render — bubble looks identical to before this change.

#### Scenario: AI bubble with suggestion_text shows apply + rephrase chips

- **GIVEN** an AI bubble with `suggestion_text = "我先了解一下，那個八折是含 SSO 跟落地嗎？"`
- **WHEN** the bubble renders
- **THEN** beneath the bubble body SHALL be two chip elements AND the first SHALL contain the text `套用為回覆` AND the second SHALL contain the text `換一個說法` with `disabled` attribute set and a `title` containing `下版本上線`

#### Scenario: Clicking apply chip sets advisor input value via callback

- **GIVEN** the advisor pane has prop `onApplySuggestion` defined and an AI bubble with `suggestion_text = "X"` is rendered
- **WHEN** the user clicks the `套用為回覆` chip
- **THEN** `onApplySuggestion` SHALL be called exactly once with the argument `"X"` AND no network request SHALL fire

#### Scenario: Rephrase chip click is a no-op

- **GIVEN** an AI bubble with `suggestion_text` set is rendered
- **WHEN** the user clicks the `換一個說法` chip
- **THEN** no callback SHALL fire AND no network request SHALL fire AND no advisor input value SHALL change

#### Scenario: AI bubble without suggestion_text shows no chip row

- **GIVEN** an AI bubble with `suggestion_text` undefined
- **WHEN** the bubble renders
- **THEN** no chip row element SHALL appear beneath the bubble body


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: AsrLoadingDialog SHALL display as a non-dismissible modal while the meeting session is connecting

A new `AsrLoadingDialog` component SHALL render as a shadcn `<Dialog>` modal whose `open` state is bound to `session.phase === "connecting"`. The dialog SHALL automatically open when the phase becomes `connecting` and SHALL automatically close when the phase transitions to `in_progress` or `error`. The dialog SHALL NOT expose a manual dismiss affordance: clicking outside the modal, pressing `Escape`, or any other dismissal gesture SHALL be a no-op (the `onOpenChange` handler ignores requests to close while phase is still `connecting`).

The dialog content SHALL contain:
1. An ElevenLabs `<BarVisualizer>` component rendered in decorative autoplay mode (no audio source required), with bar fill colour `--color-primary` and background `--color-primary-soft`, approximately 24 bars.
2. A title from i18n key `meetings.session.asrLoading.title` (zh-TW: `正在啟動轉錄引擎…` / en: `Starting transcription engine…`).
3. A subtitle from i18n key `meetings.session.asrLoading.subtitle` (zh-TW: `首次使用會下載 ASR 模型，視網路狀況可能需要 30 秒。背景下載中，請勿關閉視窗。` / en: `First-time use will download the ASR model and may take up to 30 seconds depending on network. Downloading in background — please don't close this window.`).

The component SHALL be mounted in the meeting detail page at the same DOM level as `MeetingHeaderBar` so it overlays the entire page when open.

#### Scenario: Dialog appears when session enters connecting phase

- **GIVEN** the user has clicked the 開始 button and `session.phase` transitions from `idle` to `connecting`
- **WHEN** the page re-renders
- **THEN** a modal Dialog with `data-testid="asr-loading-dialog"` SHALL be visible AND the dialog content SHALL contain the title `正在啟動轉錄引擎…` (zh-TW) AND a `<BarVisualizer>` element SHALL be present

#### Scenario: Dialog closes when session reaches in_progress

- **GIVEN** the AsrLoadingDialog is open with `session.phase === "connecting"`
- **WHEN** `session.phase` transitions to `in_progress`
- **THEN** the dialog SHALL no longer be present in the DOM

#### Scenario: Dialog closes when session enters error phase

- **GIVEN** the AsrLoadingDialog is open with `session.phase === "connecting"`
- **WHEN** `session.phase` transitions to `error`
- **THEN** the dialog SHALL no longer be present in the DOM (the error itself is surfaced by the existing inline session-error alert)

#### Scenario: Dismiss attempts during connecting are ignored

- **GIVEN** the AsrLoadingDialog is open with `session.phase === "connecting"`
- **WHEN** the user presses `Escape` OR clicks outside the modal overlay
- **THEN** the dialog SHALL remain open AND `session.phase` SHALL still be `connecting`


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: TranscriptPane SHALL animate new chunks sliding up from the bottom while keeping chronological order

The transcript chunk list inside `<TranscriptPane>` SHALL be wrapped in a framer-motion `<AnimatePresence initial={false}>` boundary. Each chunk row SHALL be a `motion.div` with:
- `initial = { opacity: 0, y: 12 }`
- `animate = { opacity: 1, y: 0 }`
- `transition = { duration: 0.2, ease: "easeOut" }`

The list SHALL maintain chronological order (oldest at top, newest at bottom). A newly arrived chunk SHALL appear at the bottom and animate into place from 12px below its final position. The `initial={false}` setting ensures that pre-existing chunks present on first mount do NOT animate together — only chunks added after first mount animate.

When the user's browser reports `prefers-reduced-motion: reduce` (via framer-motion's `useReducedMotion`), the transition `duration` SHALL be `0` (instant appearance) and `y` offset SHALL be `0` (no slide).

#### Scenario: New chunk slides up at the bottom of the list

- **GIVEN** the transcript pane has rendered chunks `[c1, c2, c3]` in chronological order with `c3` at the bottom
- **WHEN** a new chunk `c4` arrives via WebSocket and is appended to the chunks array
- **THEN** `c4` SHALL render below `c3` AND `c4`'s initial DOM `style.opacity` SHALL be `0` and `style.transform` SHALL include `translateY(12px)` AND within 200ms `c4` SHALL animate to `opacity: 1` and `translateY(0)`

#### Scenario: Existing chunks on first mount do not all animate together

- **GIVEN** the page first loads with 10 historical chunks already in the transcript
- **WHEN** the transcript pane initially mounts
- **THEN** all 10 chunks SHALL appear in their final position immediately (no fade-in cascade) — `initial={false}` SHALL skip the entrance animation for already-present items

#### Scenario: Reduced-motion users see no slide

- **GIVEN** the user has `prefers-reduced-motion: reduce`
- **WHEN** a new chunk arrives
- **THEN** the chunk SHALL appear in its final position without any transform animation AND the transition duration SHALL be `0`


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: MeetingHeaderBar SHALL render counterparty as an avatar group when the display name string contains multiple comma-separated names

When `meeting.counterparty_display_name` is split by the regex `/[,，、]\s*/` and the resulting non-empty array length is:
- `1`: MeetingHeaderBar SHALL render the existing single `<Avatar>` + name layout (unchanged from current behaviour).
- `>= 2`: MeetingHeaderBar SHALL render an `<AvatarGroup>` component containing up to **3 avatars** overlapping with z-index descending front-to-back; if the total count exceeds 3, a `+N` chip (N = total − 3) SHALL appear to the right of the avatars with background `--color-surface-2`, text `--color-muted-foreground`, `text-xs`, `rounded-full`, `size-6`. The associated name label SHALL read「{first name} 等 {N} 人」(zh-TW) / "{first name} and {N − 1} others" (en) where N is total names.

Supported separator characters: `,` (U+002C ASCII comma), `，` (U+FF0C fullwidth comma), `、` (U+3001 ideographic comma). Whitespace immediately following any separator MUST be tolerated and stripped. Whitespace alone SHALL NOT be treated as a separator.

The `<AvatarGroup>` component source SHALL be copied into `packages/web/src/components/animate-ui/avatar-group.tsx` (copy-paste pattern, NO external package install). The `meeting.counterparty_display_name` backend schema SHALL remain a single `string` column; this requirement is purely client-side parsing and presentation.

#### Scenario: Single name renders existing single avatar layout

- **GIVEN** a meeting with `counterparty_display_name = "林經理"`
- **WHEN** MeetingHeaderBar renders
- **THEN** exactly one `<Avatar>` element SHALL be present in the counterparty slot AND no `<AvatarGroup>` element SHALL be present AND the label text SHALL be `林經理`

#### Scenario: Two comma-separated names render as avatar group

- **GIVEN** a meeting with `counterparty_display_name = "林經理, 王董"`
- **WHEN** MeetingHeaderBar renders
- **THEN** an `<AvatarGroup>` element SHALL be present containing exactly 2 avatars AND no `+N` chip SHALL be visible AND the label text SHALL contain `林經理 等 2 人` (zh-TW)

#### Scenario: Five names render three avatars plus +2 chip

- **GIVEN** a meeting with `counterparty_display_name = "林經理、王董, 陳副總，黃工程師、Joyce"`
- **WHEN** MeetingHeaderBar renders
- **THEN** an `<AvatarGroup>` element SHALL contain exactly 3 avatars AND a chip with text `+2` SHALL be visible to the right AND the label text SHALL contain `林經理 等 5 人` (zh-TW)

#### Scenario: All three separator characters are recognised

- **GIVEN** a meeting with `counterparty_display_name = "A,B，C、D"` (mixed separators)
- **WHEN** MeetingHeaderBar renders
- **THEN** the parsed array SHALL be `["A", "B", "C", "D"]` AND an `<AvatarGroup>` SHALL render exactly 3 avatars plus a `+1` chip


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Recording status indicator SHALL render four states derived from meeting bucket and recordings availability, never using grey

MeetingHeaderBar's recording status indicator SHALL be rendered by a pure function `resolveRecordingStatus(meeting)` exported from `packages/web/src/lib/meetings-recording-status.ts` returning one of four states:

| State | Trigger condition | Colour token | i18n key (label) |
|---|---|---|---|
| `available` | `meeting.recordings_available === true` | `--color-success` (green) | `meetings.detail.recordingAvailable` |
| `pending` | `bucket === "needs_recording"` (meeting time has passed but no recording uploaded) | `--color-warning` (orange) | `meetings.detail.recordingPending` (new key) |
| `expired` | `bucket === "completed"` AND `!recordings_available` | `--color-accent` (mauve magenta) | `meetings.detail.recordingExpired` |
| `hidden` | `bucket === "upcoming"` (meeting has not yet occurred) | — (no indicator rendered) | — |

The new i18n key `meetings.detail.recordingPending` SHALL have values:
- zh-TW: `待上傳`
- en: `Pending upload`

The indicator MUST NOT use `--color-muted-foreground`, `--color-surface-3`, or any other grey-coded token; Sean explicitly rejected grey as too lifeless for past-tense states. When `expired` and `pending` need to be visually distinct without grey, the system uses mauve (accent) for expired (past-tense, static feel) and orange (warning) for pending (call to action).

#### Scenario: Available state renders green dot with 錄音可用 label

- **GIVEN** a meeting with `recordings_available = true` and any bucket
- **WHEN** MeetingHeaderBar renders
- **THEN** the recording indicator SHALL be visible with a coloured dot using `--color-success` AND the label text SHALL be `錄音可用` (zh-TW)

#### Scenario: Pending state renders orange dot with 待上傳 label

- **GIVEN** a meeting with `bucket === "needs_recording"` (meeting passed, no recording yet uploaded)
- **WHEN** MeetingHeaderBar renders
- **THEN** the recording indicator SHALL be visible with a coloured dot using `--color-warning` AND the label text SHALL be `待上傳` (zh-TW)

#### Scenario: Expired state renders mauve dot with 錄音已過期 label

- **GIVEN** a meeting with `bucket === "completed"` AND `recordings_available === false`
- **WHEN** MeetingHeaderBar renders
- **THEN** the recording indicator SHALL be visible with a coloured dot using `--color-accent` AND the label text SHALL be `錄音已過期` (zh-TW)

#### Scenario: Upcoming meeting hides the indicator entirely

- **GIVEN** a meeting with `bucket === "upcoming"` (status scheduled, future time)
- **WHEN** MeetingHeaderBar renders
- **THEN** no recording indicator element SHALL be present in the DOM (neither the dot nor the label)

#### Scenario: Grey colour tokens are never used for the indicator

- **GIVEN** any meeting where the recording indicator renders
- **WHEN** the indicator's coloured dot element is inspected
- **THEN** its computed background colour SHALL NOT resolve to `--color-muted-foreground`, `--color-surface-3`, or any equivalently desaturated grey token


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Playbook column SHALL render its six fields using animate-ui Radix Accordion with height animation, replacing manual expand/collapse state

The Playbook column's six fields (目標 / 對方輪廓 / 預期主題 / 預期反對 / 談話要點 / 紅線) SHALL be rendered using the animate-ui Radix Accordion component (copy-pasted into `packages/web/src/components/animate-ui/radix-accordion.tsx`, built on top of `@radix-ui/react-accordion` + framer-motion height animation). The previous manual `PlaybookField` component with `useState`-driven expand state SHALL be removed.

The accordion SHALL be configured with `type="multiple"` so that the user MAY expand more than one field simultaneously (the six playbook fields are often referenced together, e.g. comparing `紅線` against `談話要點`). The default expanded set SHALL be `["objective", "talkingPoints"]` (目標 + 談話要點 — the two most frequently consulted during a live meeting).

Each `<AccordionItem>` SHALL use its field's stable key as its `value` attribute (e.g. `objective`, `counterpartyProfile`, `anticipatedTopics`, `anticipatedObjections`, `talkingPoints`, `redLines`). The trigger row SHALL render the field title from its existing i18n key plus a chevron icon supplied by the accordion component (no separate manually-rendered chevron). The content panel SHALL contain the field's markdown body.

#### Scenario: Six accordion items render with default-expanded objective and talkingPoints

- **GIVEN** a playbook with all six fields populated
- **WHEN** the Playbook column renders
- **THEN** exactly six `<AccordionItem>` elements SHALL be present with values `objective`, `counterpartyProfile`, `anticipatedTopics`, `anticipatedObjections`, `talkingPoints`, `redLines` (in that document order) AND the `objective` and `talkingPoints` triggers SHALL have `aria-expanded="true"` AND the other four triggers SHALL have `aria-expanded="false"`

#### Scenario: Clicking a collapsed trigger expands its panel without collapsing others

- **GIVEN** the Playbook column is rendered with `objective` and `talkingPoints` expanded
- **WHEN** the user clicks the `redLines` trigger
- **THEN** `redLines` trigger SHALL update to `aria-expanded="true"` AND its content panel SHALL animate to its full height AND the `objective` and `talkingPoints` panels SHALL remain expanded (multi-mode behaviour)

#### Scenario: Manual PlaybookField component is removed

- **WHEN** the codebase is grepped for the symbol `PlaybookField`
- **THEN** no source file under `packages/web/src/` SHALL define or import `PlaybookField` (it is replaced by accordion items inside `<PlaybookPane>`)


<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: SuccessResultOverlay SHALL render after upload audio and export bundle async operations complete, with backdrop blur and auto-dismiss

A new `SuccessResultOverlay` component SHALL render a fixed-position modal-style overlay with a backdrop blur ("hazeover" effect: `fixed inset-0 bg-black/30 backdrop-blur-sm z-[60]` + centered content). It SHALL be wired to two async completion events on the detail page:

1. **Upload audio completes** — after `UploadDialog` finishes the offline ingest pipeline (its existing `state === "done"` signal), the dialog closes and `SuccessResultOverlay` renders with title from `meetings.detail.uploadSuccessTitle` (`音檔處理完成` / `Audio processed`), subtitle from `meetings.detail.uploadSuccessSubtitle` (`逐字稿已自動生成` / `Transcript generated`), `autoDismissMs = 3000`, and a primary action button labeled `meetings.detail.viewTranscript` (`查看逐字稿` / `View transcript`) which, when clicked, focuses the workspace tab's transcript column then closes the overlay.

2. **Export ZIP completes** — after `ExportMeetingButton` triggers the browser download (its existing success path), `SuccessResultOverlay` renders with title from `meetings.detail.exportSuccessTitle` (`匯出完成` / `Export complete`), subtitle from `meetings.detail.exportSuccessSubtitle` (`ZIP 已儲存到下載資料夾` / `ZIP saved to Downloads`), `autoDismissMs = 3000`, and no primary action.

Component contract:

- `props`: `{ open: boolean; title: string; subtitle?: string; autoDismissMs?: number; onClose: () => void; primaryAction?: { label: string; onClick: () => void } }`
- When mounted with `open === true` AND `autoDismissMs > 0`, the component SHALL call `onClose` after the specified duration via `setTimeout`.
- Pressing `Escape` SHALL call `onClose`. Clicking the backdrop element (not the centered card) SHALL call `onClose`.
- Clicking the primary action button SHALL invoke `primaryAction.onClick` then `onClose`.
- The success visual SHALL include a check-mark indicator (Lucide `CircleCheck` or the DevSloka prebuilt animation) — no emoji.

The overlay SHALL be mounted in `detail.tsx` at the same DOM level as `MeetingHeaderBar`. State variables `uploadSuccessOpen` and `exportSuccessOpen` SHALL be managed in `detail.tsx`, with `UploadDialog` and `ExportMeetingButton` notifying via `onSuccess` callbacks.

#### Scenario: Upload completion shows overlay with view-transcript action

- **GIVEN** a meeting with `bucket === "needs_recording"` and the user has opened the UploadDialog and selected an audio file
- **WHEN** the upload + processing pipeline completes (UploadDialog reaches its `done` state)
- **THEN** the UploadDialog SHALL close AND a `SuccessResultOverlay` SHALL appear with title text `音檔處理完成` AND a backdrop element with class containing `backdrop-blur-sm` SHALL be present AND a primary action button with text `查看逐字稿` SHALL be visible

#### Scenario: Export completion shows overlay without primary action

- **GIVEN** the user has clicked the 匯出 button and the ZIP bundle has been prepared and triggered for download
- **WHEN** the export success callback fires
- **THEN** a `SuccessResultOverlay` SHALL appear with title text `匯出完成` AND no primary action button SHALL be present

#### Scenario: Overlay auto-dismisses after 3 seconds

- **GIVEN** a `SuccessResultOverlay` is open with `autoDismissMs = 3000`
- **WHEN** 3000 milliseconds have elapsed since mount
- **THEN** `onClose` SHALL have been called exactly once AND the overlay SHALL no longer be in the DOM

#### Scenario: Escape and backdrop click dismiss immediately

- **GIVEN** a `SuccessResultOverlay` is open
- **WHEN** the user presses `Escape`
- **THEN** `onClose` SHALL be called immediately

- **GIVEN** a `SuccessResultOverlay` is open
- **WHEN** the user clicks the backdrop element (outside the centered card)
- **THEN** `onClose` SHALL be called immediately

#### Scenario: Hazeover backdrop covers the entire viewport

- **GIVEN** a `SuccessResultOverlay` is open at 1440px viewport
- **WHEN** the backdrop element is inspected
- **THEN** it SHALL have `position: fixed` covering the full viewport (`inset-0`) AND `z-index >= 50` AND a Tailwind class containing `backdrop-blur` AND a background colour with opacity making the underlying page visibly dimmed but still discernible (not fully opaque)

<!-- @trace
source: refactor-meeting-detail-three-column
updated: 2026-05-20
code:
  - packages/web/src/components/asr-loading-dialog.tsx
  - packages/web/src/components/workspace.tsx
  - packages/web/src/lib/meetings-recording-status.ts
  - packages/web/src/components/animate-ui/avatar-group.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/meeting-meta-strip.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/components/export-meeting-button.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/layout-switcher.tsx
  - packages/web/src/components/success-result-overlay.tsx
  - packages/web/src/components/meeting-header-bar.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-overflow-menu.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/pane.tsx
  - bun.lock
  - packages/web/src/components/animate-ui/radix-accordion.tsx
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meeting-detail-summary-view.tsx
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/hooks/use-detail-layout.ts
tests:
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/meeting-overflow-menu.test.tsx
  - packages/web/src/components/asr-loading-dialog.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-header-bar.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/meetings-recording-status.test.ts
  - packages/web/src/components/meeting-detail-summary-view.test.tsx
  - packages/web/src/components/success-result-overlay.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
-->