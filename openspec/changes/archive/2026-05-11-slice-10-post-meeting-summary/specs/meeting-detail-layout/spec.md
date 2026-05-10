## ADDED Requirements

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
