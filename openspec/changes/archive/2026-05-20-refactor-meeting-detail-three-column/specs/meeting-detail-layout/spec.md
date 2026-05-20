## REMOVED Requirements

### Requirement: Detail page exposes a layout switcher persisted across sessions

**Reason**: The desktop-only meeting detail page always uses three columns now. The two-mode switcher (`stack` / `columns`) added complexity without benefit — `stack` mode was never the user's actual working mode. The `LayoutSwitcher` component, `useDetailLayout` hook, and `localStorage["meeting-detail.layout"]` key are removed.

**Migration**: No data migration. The `meeting-detail.layout` localStorage key in user browsers becomes inert (no code reads it); residual values are harmless. Users who relied on stack mode SHALL have no alternative — the desktop-only product no longer supports it.

### Requirement: Stack mode renders the three panes vertically in P-T-A order

**Reason**: Stack mode is removed (see "Detail page exposes a layout switcher persisted across sessions" REMOVED above). The workspace SHALL always render the three columns horizontally.

**Migration**: Replaced by "Workspace SHALL always render the three columns side-by-side" (see ADDED below).

### Requirement: Columns mode renders three panes in a 30/40/30 grid with full-width meta

**Reason**: "Columns mode" no longer exists as an alternative — three columns are the only layout. The 30/40/30 proportion is replaced by equal-width columns to give the playbook and advisor sides the same visual weight as the transcript. The "full-width meta card" requirement is superseded by the new `MeetingHeaderBar` row (see ADDED below).

**Migration**: Replaced by "Workspace SHALL render three equal-width columns above which sits a MeetingHeaderBar row" (see ADDED below). Existing `data-testid="detail-pane-playbook|transcript|advisor"` hooks SHALL remain available on the column content wrappers for backwards-compatible test selectors.

### Requirement: Columns mode three panes share equal visible height (slice-7 round 2)

**Reason**: "Columns mode" is now the only mode; the conditional ("ONLY in columns mode") clause is no longer meaningful.

**Migration**: Replaced by "The three workspace columns SHALL share an identical computed height" (see ADDED below), with the same target formula (viewport minus header stack), and the same independent per-column scroll behavior.

### Requirement: MetadataCard SHALL render as a two-column layout with embedded CaptureIndicator

**Reason**: The MetadataCard component is removed entirely. Its responsibilities split into:
- Core meta (title / status / scheduled time / 對方 / 我方 / capture indicator) → new `MeetingHeaderBar` row.
- Eight secondary affordances (edit / tags / attachments / linked / ASR / mode / rerun / delete) → new `MeetingOverflowMenu` opened from the header bar.

**Migration**: Replaced by "MeetingHeaderBar SHALL render core metadata as a single horizontal row" and "MeetingOverflowMenu SHALL consolidate eight secondary affordances" (see ADDED below).

### Requirement: Workspace layout SHALL switch between three-column and stacked via animate-ui

**Reason**: Stack mode is removed (see REMOVED above). No layout switching occurs; cross-fade animation between layouts is no longer relevant.

**Migration**: No replacement. The `<Workspace>` component still exists but its `layout` prop is removed.

### Requirement: Detail page metadata card exposes ASR provider selector, recording badge, and re-run action

**Reason**: The metadata card itself is removed (see "MetadataCard SHALL render as a two-column layout" REMOVED above). The three sub-elements relocate:
- **AsrProviderSelector** → opened from `MeetingOverflowMenu` "ASR Provider" item as a popover.
- **RecordingBadge** (the "錄音可用/已過期" coloured-dot row) → kept inline in `MeetingHeaderBar` second row (compact format).
- **RerunButton** → triggered from `MeetingOverflowMenu` "Rerun ASR" item (the in-flight overlay in the transcript pane still appears as before).

**Migration**: Replaced by "MeetingHeaderBar SHALL display a recording availability indicator" (see ADDED below) plus "MeetingOverflowMenu SHALL include items for ASR Provider, Recording mode, and Rerun ASR" (see ADDED below).

### Requirement: Meeting detail page renders an Attachments section with the dropzone component

**Reason**: The inline Attachments section consumed significant vertical space for a feature used a few times per meeting. The dropzone moves into a dialog opened from `MeetingOverflowMenu` "Attachments (N)" item, where N is the attachment count badge.

**Migration**: Replaced by "MeetingOverflowMenu SHALL include an Attachments item that opens a dialog containing AttachmentDropzone" (see ADDED below). The `meeting-detail-attachments-section` test selector is removed; new selector `meeting-attachments-dialog` SHALL appear on the dialog.

### Requirement: MetadataCard header renders a related-meetings section between prev/next nav and meta

**Reason**: The MetadataCard is removed (see REMOVED above). Related-meeting links no longer have a dedicated inline section; they move into a dialog opened from `MeetingOverflowMenu` "Linked meetings (N)" item.

**Migration**: Replaced by "MeetingOverflowMenu SHALL include a Linked meetings item that opens a dialog containing MeetingLinksSection" (see ADDED below).

## MODIFIED Requirements

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

## ADDED Requirements

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

### Requirement: The three workspace columns SHALL share an identical computed height with independent scrolling

The three workspace columns SHALL render at IDENTICAL visible height so the row presents as a balanced grid rather than a jagged silhouette. The shared height SHALL be derived from the available viewport height minus the page top stack (prev/next nav + MeetingHeaderBar + conditional alerts + tabs) and the bottom MeetingAudioMiniPlayer height (target: approximately `calc(100vh - 280px)` give-or-take a few pixels; exact value SHALL be derived at runtime via measured CSS variables). Content overflow within any column SHALL be confined to that column's own scroll container so a long transcript does not push other columns downward.

#### Scenario: Columns are visually balanced with independent scrolls

- **GIVEN** detail page workspace tab on a 1440-wide viewport with a tall transcript and a short playbook
- **WHEN** the page renders
- **THEN** the three column wrappers SHALL have equal computed heights (within 1px tolerance) AND each column's internal scroll container SHALL be independent (scrolling one does not move the others)

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
