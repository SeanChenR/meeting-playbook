## ADDED Requirements

### Requirement: Pre-flight recording mode selector chooses dual-channel or single-channel capture

The meeting detail page SHALL render a Recording Mode selector while the meeting `status` is `scheduled`. The selector SHALL present exactly two mutually-exclusive options labelled per locale as Dual-channel capture (me + counterparty) and Single-channel (mic only). The default selection SHALL be `dual` for every new session and SHALL NOT be persisted across sessions or to server-side state. The selector SHALL be hidden (not just disabled) once `status` advances to `in_progress` or `completed`. The `HeadphonesHint` callout SHALL render ONLY when the selector value is `dual`.

The client SHALL include the selected mode in the `start_meeting` WebSocket frame as the field `mode` with the literal value `"dual"` or `"single"`. The backend Pydantic model for `StartMeetingMessage` SHALL accept `mode` with default `"dual"` when the field is absent (backwards compatibility for older clients), accept the literal values `"dual"` and `"single"`, and reject any other value with a `ValidationError` that the router maps to `error_code: session.unknown_message`. Once `start_meeting` has been accepted the mode SHALL be immutable for the lifetime of that WebSocket; no client frame, server frame, or REST endpoint SHALL mutate the live session's mode.

#### Scenario: Default mode is dual on a freshly opened scheduled meeting

- **GIVEN** a meeting `m_abc` with `status = "scheduled"`
- **WHEN** the user navigates to `/meetings/m_abc`
- **THEN** the Recording Mode selector SHALL be visible with `dual` selected and the `HeadphonesHint` callout SHALL be visible

#### Scenario: Switching to single hides the HeadphonesHint callout

- **GIVEN** the Recording Mode selector is visible with value `dual`
- **WHEN** the user picks the Single-channel option
- **THEN** the selector value SHALL change to `single` and the `HeadphonesHint` callout SHALL no longer render

#### Scenario: Selector value is sent with the start_meeting frame

- **GIVEN** the user has chosen Single-channel mode for meeting `m_abc`
- **WHEN** the user clicks Start Meeting
- **THEN** the WebSocket client SHALL send `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "single"}` as the first frame after WS open

#### Scenario: Selector is hidden once the session starts

- **GIVEN** a meeting whose `status` has just advanced to `in_progress`
- **WHEN** the meeting detail page re-renders
- **THEN** the Recording Mode selector SHALL NOT be rendered and the user MUST NOT have any UI affordance to change `mode` mid-session

#### Scenario: Backwards-compatible start frame with no mode field defaults to dual

- **GIVEN** an older client that has not been updated
- **WHEN** the server receives `{"type": "start_meeting", "meeting_id": "m_abc"}` (no `mode` field)
- **THEN** the backend Pydantic parser SHALL accept the frame and treat `mode` as `"dual"`; the dual-channel pre-flight path (BlackHole + microphone) SHALL run unchanged

#### Scenario: Invalid mode value is rejected before any session state changes

- **WHEN** the server receives `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "invalid"}`
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.unknown_message"}` and close the WebSocket; the meeting row SHALL retain `status = "scheduled"` and no `recording` row SHALL be written

#### Scenario: Mode does not persist across sessions

- **GIVEN** a meeting `m_abc` whose previous session ran in `single` mode and ended
- **WHEN** the user starts a new session on a different meeting OR re-opens `/meetings/m_abc` after `m_abc` has been re-scheduled
- **THEN** the Recording Mode selector SHALL default to `dual` for the new session

##### Example: mode field boundary cases

| Incoming start_meeting frame | Parsed `mode` | Pre-flight check | Outcome |
| ---------------------------- | ------------- | ---------------- | ------- |
| `{"type":"start_meeting","meeting_id":"x"}` | `"dual"` (default) | BlackHole + mic | dual-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"dual"}` | `"dual"` | BlackHole + mic | dual-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"single"}` | `"single"` | mic only (NO BlackHole check) | single-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"both"}` | rejected | n/a | `session.unknown_message`; status stays `scheduled` |
| `{"type":"start_meeting","meeting_id":"x","mode":null}` | rejected | n/a | `session.unknown_message`; status stays `scheduled` |

## MODIFIED Requirements

### Requirement: Pre-flight check rejects session start when BlackHole device is missing

Before opening any capture stream the session SHALL inspect the `mode` field of the accepted `start_meeting` frame and invoke a device-discovery routine accordingly.

When `mode == "dual"` the session SHALL locate a BlackHole device by name pattern. The routine SHALL match any input device whose `name` contains the substring `BlackHole` and whose `max_input_channels` is at least 2, OR the device whose name exactly equals the value of the optional `BLACKHOLE_DEVICE_NAME` environment variable when that variable is set. If no matching device exists, the session SHALL emit `{"type": "error", "error_code": "session.no_blackhole_device", "message": "<localized>"}` and close the WebSocket connection without writing any `recording` row, without transitioning the meeting status, and without spawning any capture task. The localized message SHALL include a hint that the user can switch to `single` mode as an alternative.

When `mode == "single"` the session MUST NOT invoke the BlackHole discovery routine and MUST NOT emit `session.no_blackhole_device` regardless of whether a BlackHole device is present, absent, or misconfigured. The microphone discovery routine SHALL still run in both modes; a missing microphone SHALL emit `error_code: session.no_audio_device` and abort the session in both modes.

The pre-flight SHALL NOT attempt to verify that the system audio output is routed through a Multi-Output Device in either mode.

#### Scenario: Missing BlackHole device aborts a dual-mode session

- **GIVEN** the host machine has no input device whose name contains `BlackHole`
- **WHEN** an authenticated owner sends `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "dual"}`
- **THEN** the server SHALL respond with `{"type": "error", "error_code": "session.no_blackhole_device"}` and close the connection; the meeting row SHALL retain `status = "scheduled"` and no `recording` row SHALL be written

#### Scenario: Missing BlackHole device does NOT abort a single-mode session

- **GIVEN** the host machine has no input device whose name contains `BlackHole` and the microphone is available
- **WHEN** an authenticated owner sends `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "single"}`
- **THEN** the server MUST NOT emit `session.no_blackhole_device`; the BlackHole discovery routine MUST NOT be invoked; the session SHALL proceed to open the microphone stream and emit `meeting_started`

#### Scenario: Missing microphone aborts both modes

- **GIVEN** the host has no system default input device and no `MIC_DEVICE_NAME` override that resolves
- **WHEN** an authenticated owner sends `start_meeting` in either `dual` or `single` mode
- **THEN** the server SHALL respond with `{"type": "error", "error_code": "session.no_audio_device"}` and close the connection; the meeting row SHALL retain `status = "scheduled"`

#### Scenario: BLACKHOLE_DEVICE_NAME env override locates a non-default device in dual mode

- **GIVEN** the host has two BlackHole-related devices and `BLACKHOLE_DEVICE_NAME=BlackHole 16ch` is set
- **WHEN** the dual-mode session pre-flight runs
- **THEN** the routine SHALL select the device named exactly `BlackHole 16ch` rather than the auto-detected `BlackHole 2ch` device

#### Scenario: BLACKHOLE_DEVICE_NAME env override is ignored in single mode

- **GIVEN** `BLACKHOLE_DEVICE_NAME=BlackHole 16ch` is set but no such device exists
- **WHEN** the user starts a session with `mode = "single"`
- **THEN** the env override SHALL NOT be consulted and the session SHALL start successfully on the microphone stream

### Requirement: Session captures BlackHole and microphone as two parallel streams with independent failure domains

For dual-mode sessions, the `SessionService` SHALL hold two `AudioCaptureService` instances: one for the microphone (stream label `me`, device resolved via `MIC_DEVICE_NAME` env override or `sounddevice.default.device[0]`) and one for BlackHole (stream label `counterparty`, device resolved per the pre-flight routine above). The two instances SHALL produce `AudioChunk` events independently, each labelled with its stream identifier. At session start both streams MUST successfully open their respective `RawInputStream` before the server emits `meeting_started`; if either fails to open the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection. Once the session is running, an exception in one stream's capture task SHALL stop only that stream — the other stream MUST continue producing chunks until the user ends the meeting OR the second stream also stops.

For single-mode sessions, the `SessionService` SHALL hold exactly ONE `AudioCaptureService` instance for the microphone (stream label `me`). No `counterparty` capture instance SHALL be constructed and the `providers` mapping SHALL contain only the `me` entry so the per-stream ASR routing invariant from the warmup requirement is preserved. The microphone stream MUST open successfully before the server emits `meeting_started`; if it fails to open the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection. At finalize, single-mode sessions SHALL produce at most ONE recording row with `stream = "me"`; no `counterparty` recording row SHALL be inserted.

#### Scenario: Both streams open and produce parallel chunks in dual mode

- **GIVEN** the host has both a working BlackHole device and a working microphone, and a meeting `m_abc` is in `scheduled` status
- **WHEN** the user starts the session in `dual` mode via WebSocket
- **THEN** the server SHALL emit `meeting_started` followed by `transcript_chunk` messages for both `speaker = "me"` and `speaker = "counterparty"`, each chunk derived only from its corresponding source stream

#### Scenario: One stream failing at start aborts the whole dual-mode session

- **GIVEN** the BlackHole device is present but the microphone open call raises (e.g., system permission revoked)
- **WHEN** the dual-mode session pre-flight plus `start()` runs
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection without producing any `recording` row

#### Scenario: Single-mode session opens exactly one microphone stream

- **GIVEN** the host has a working microphone (BlackHole may or may not be present)
- **WHEN** the user starts the session in `single` mode via WebSocket
- **THEN** the server SHALL construct exactly one `AudioCaptureService` with `stream_label = "me"`, emit `meeting_started`, and emit `transcript_chunk` messages only for `speaker = "me"`; no `counterparty` chunk SHALL be sent

#### Scenario: Single-mode session writes exactly one recording row at finalize

- **GIVEN** a single-mode session has run and the user has ended the meeting
- **WHEN** the router runs the finalize block
- **THEN** the database SHALL contain exactly one new `recording` row for the meeting with `stream = "me"`, file path `{recordings_dir}/{meeting_id}/me.wav`, and no `counterparty` recording row
