# Sessions — agent notes

> Slice 6 (`slice-06-mic-transcript-session`) outcome.
> Spec: `openspec/specs/meeting-session/spec.md` (after archive).
> Module: `packages/backend/meeting_playbook/sessions/` + `audio/` + `asr/`.

## End-to-end flow

```
Browser
  └─ Meeting detail page
       │ user clicks "開始會議 / Start Meeting"
       ▼
  useMeetingSession(meetingId)
       │ opens WS via openSessionSocket
       │ reducer manages SessionState
       ▼
Bun gateway (sole ingress)
  └─ /api/meetings/:id/session — WS upgrade with X-User-Id / X-User-Name / X-User-Email
       ▼
FastAPI WebSocket router (sessions/router.py)
  ├─ ownership gate via MeetingRepository.get_for_user → close 4404 on miss
  ├─ first client message MUST be start_meeting (matching path id)
  ├─ MeetingRepository.transition_status: scheduled → in_progress
  ├─ AudioCaptureService(meeting_id) yields AudioChunk + SilenceWarning
  ├─ SessionService.run(capture):
  │   AudioChunk → ASRProvider.transcribe_chunk → SessionRepository.insert_chunk
  │                → outbound transcript_chunk frame
  │   SilenceWarning → outbound silence_warning frame (deduped per window)
  ├─ end_meeting from client OR client disconnect → finalize:
  │   recording row inserted, MeetingRepository.transition_status → completed,
  │   meeting_ended frame, WS close
  ▼
PostgreSQL
  ├─ meeting (status transitions tracked, updated_at touched)
  ├─ transcript_chunk (one row per ASR chunk, ordered by started_at)
  └─ recording (one WAV per stream per meeting)

WAV file → {RECORDINGS_DIR}/{meeting_id}/me.wav (atomic .tmp → rename on exit)
```

## WS message contract

Mirror across:
- Backend Pydantic: `meeting_playbook.sessions.messages`
- Frontend TypeScript: `packages/web/src/lib/session-ws.ts`

| `type`              | Required keys                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `start_meeting`     | `type`, `meeting_id`                                                                                       |
| `end_meeting`       | `type`, `meeting_id`                                                                                       |
| `meeting_started`   | `type`, `meeting_id`                                                                                       |
| `transcript_chunk`  | `type`, `meeting_id`, `speaker`, `text`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`       |
| `silence_warning`   | `type`, `meeting_id`, `since`                                                                              |
| `meeting_ended`     | `type`, `meeting_id`                                                                                       |
| `error`             | `type`, `error_code`, `message`                                                                            |

Adding a new server-side type is a breaking change to the contract: add the
Pydantic model, the TS type, the spec example matrix row, and a test.

## ASRProvider invariant

The session router MUST NOT import any concrete provider. It depends only
on the `meeting_playbook.asr.base.ASRProvider` Protocol; the concrete
provider is injected via the `get_asr_provider_dependency` FastAPI
dependency. Adding a second provider (Slice 12 VibeVoice) is a drop-in by
implementing the Protocol; do NOT modify the router or AudioCaptureService.

## AudioCaptureService lifecycle

`AudioCaptureService` is an **async context manager**. Standard usage:

```python
async with AudioCaptureService(
    meeting_id="m_abc",
    recordings_dir=Path("~/MeetingPlaybook/recordings").expanduser(),
) as session:
    async for event in session.events():
        # AudioChunk or SilenceWarning
        ...
# On exit: WAV finalized at {recordings_dir}/{meeting_id}/me.wav
```

The default factory opens a real `sounddevice.RawInputStream` on the system
default input device. Tests inject `_input_stream_factory` to script
deterministic PCM frames.

`RECORDINGS_DIR` defaults to `~/MeetingPlaybook/recordings`. The directory
is created lazily on `__aenter__`. Recordings are stored under the user's
home dir (NOT the project tree) so `git clean -fdx` and worktree switches
do not destroy private audio. `.gitignore` defensively blocks `*.wav`
outside `tests/**`.

## Status transition invariant

`meeting.status` is written ONLY via `MeetingRepository.transition_status`.
Allowed transitions: `scheduled → in_progress`, `in_progress → completed`.
Any other pair (backwards, repeated, skipping) raises
`MeetingStatusConflict`. Do NOT add `UPDATE meeting SET status` SQL
elsewhere.

## macOS microphone permission

First time a user clicks "Start Meeting" after a fresh terminal restart,
macOS prompts for microphone access. If denied:
- The `sounddevice.RawInputStream` constructor raises `PortAudioError`
- `AudioCaptureService` wraps it as `CaptureDeviceUnavailable`
- The router currently lets that propagate to the WS client as a generic
  `error` frame; future work could map it to `error_code: session.no_audio_device`
  for a localized "請打開麥克風權限" UI prompt

To regrant after deny: **System Settings → Privacy & Security → Microphone**
and enable the terminal / Python process.
