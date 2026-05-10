## ADDED Requirements

### Requirement: Meeting end finalize spawns a fire-and-forget summary generation task

When the WebSocket session handler `meeting_session_endpoint` finishes its finalize block (recording rows persisted, meeting status transitioned to `completed`, `meeting_ended` frame sent, WebSocket closed), the handler SHALL invoke `summarization.runtime.spawn_summary_task(meeting_id)` BEFORE returning. The call SHALL be fire-and-forget — the handler MUST NOT `await` the spawned task. The spawned task runs in the background, and its outcome (success or failure) is observable only via `GET /api/meetings/{id}/summary` and the backend log.

The spawn SHALL run only when the meeting actually transitioned to `completed` during this session (not when status was already `completed` from a prior session, and not when finalize raised partway through). If `runtime.spawn_summary_task` returns `False` (a prior session's task is still running), the handler SHALL log an info-level message and proceed to return without raising.

The fire-and-forget invocation SHALL NOT introduce any new WebSocket frame, SHALL NOT delay the WebSocket close handshake, and SHALL NOT change the existing `meeting_ended` semantics.

#### Scenario: Successful end_meeting spawns a summary task without blocking the response

- **GIVEN** an `in_progress` WebSocket session
- **WHEN** the client sends `end_meeting` and the finalize block completes (status → completed, `meeting_ended` sent)
- **THEN** `runtime.is_pending(meeting_id)` SHALL return `True` immediately after the WebSocket closes AND the WebSocket close handshake SHALL NOT have been delayed by waiting on the summary generation

#### Scenario: end_meeting on an already-completed session does not double-spawn

- **GIVEN** a meeting whose status was already `completed` from a prior aborted attempt AND a summary task already running for it
- **WHEN** the WebSocket finalize block runs (which is a no-op for status transition because it's already completed)
- **THEN** `runtime.spawn_summary_task` SHALL return `False` AND the handler SHALL log an info message AND no second background task SHALL be created

#### Scenario: WebSocket close timing is independent of summary generation duration

- **GIVEN** a stub `MeetingSummarizer` whose `summarize` sleeps 30 seconds
- **WHEN** the client sends `end_meeting`
- **THEN** the WebSocket SHALL receive `meeting_ended` and close within 5 seconds (the same upper bound as without the summary spawn) AND the summary task SHALL still be running in the background
