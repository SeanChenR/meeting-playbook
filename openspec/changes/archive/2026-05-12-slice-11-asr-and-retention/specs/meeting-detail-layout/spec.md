## ADDED Requirements

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
