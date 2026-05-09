## Context

This is the foundation slice for the entire in-meeting domain. All later slices depend on it:
- Slice 7 adds the BlackHole second stream → needs `AudioCaptureService` shape that supports multiple streams + `transcript_chunk.speaker = "counterparty"`
- Slice 8 (tactical advisor) consumes the same `transcript_chunk` stream → server-side broadcast pattern needs to support a second consumer
- Slice 12 (VibeVoice) is a second `ASRProvider` impl → the interface defined here is the keystone (per ADR-0005)

So design choices here have downstream consequences. This design document over-invests in the WebSocket contract, the ASRProvider interface, and the AudioCaptureService boundaries — they will be re-read by every subsequent in-meeting slice.

Slice 5 already established: gateway sets `X-User-Id` + `X-User-Name` + `X-User-Email` on every authenticated `/api/*` request (URL-encoded). Slice 3 already established the `meeting` row including `status` (`scheduled` / `in_progress` / `completed`) and `me_display_name` / `counterparty_display_name`. Slice 4 established `playbook` 1:1 with meeting. Slice 5 made `me_display_name` actually meaningful (Better Auth user.name not the literal "Me").

## Goals / Non-Goals

**Goals:**

- One-click Start Meeting → within 10–15 seconds the first transcript chunk renders in the UI
- Subsequent chunks arrive at ~10s intervals until End Meeting
- Capture indicator clearly shows audio is being received; >30s silence surfaces a warning
- WAV file persisted to `{RECORDINGS_DIR}/{meeting_id}/me.wav` after the meeting ends
- Meeting `status` correctly transitions scheduled → in_progress → completed
- ASRProvider interface is concrete enough that a second impl (VibeVoice in Slice 12) can drop in without changing AudioCaptureService or sessions/router
- TDD: every layer (capture, ASR, repository, service, router, hook, component) has its own RED → GREEN cycle

**Non-Goals:**

- BlackHole second stream (Slice 7)
- Diarization within one stream
- Tactical advisor / playbook live updates / summary
- Recording cleanup, retention, encryption-at-rest
- Reconnect after browser tab close
- Multi-device session sync
- Production-grade WAV streaming (we write entire file at end-of-session; not streaming-to-disk)
- Auto-download Whisper model with progress UI; first run downloads on demand and the README documents it

## Decisions

### ASRProvider interface (per ADR-0005, formalized here)

Defined in `packages/backend/meeting_playbook/asr/base.py`:

```python
@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    started_at: datetime  # absolute UTC, derived from chunk start in capture session
    ended_at: datetime
    asr_provider_used: str  # provider.name
    confidence: float | None  # 0..1, optional

class ASRProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk: ...
```

Design choices:
- **Bytes in, dataclass out** — keeps the interface decoupled from numpy / soundfile / specific in-memory shapes. Provider impls convert as needed.
- **Async** — even sync impls (faster-whisper is sync) wrap the call in `asyncio.to_thread` so the WS event loop stays unblocked.
- **`sample_rate_hz` explicit** — providers MUST NOT assume 16kHz; future providers may need different sample rates and the capture service knows the truth.
- **`language_hint` optional** — Whisper auto-detects; for `zh-TW` we pass `"zh"` to nudge it.
- **`confidence`** is `float | None` because not all providers expose it cleanly.

### WhisperProvider lazy model load

`packages/backend/meeting_playbook/asr/whisper_provider.py` — wraps `faster_whisper.WhisperModel`. Constructor stores config but does NOT load the model. First `transcribe_chunk` call loads it (`~1.5GB`, several seconds the first run). Subsequent calls reuse the loaded model. Model size, device (`cpu` / `cuda` / `auto`), compute type read from Settings (env-driven); on macOS Apple Silicon dev the default `auto` selects CPU + int8 — adequate for slice-6 demo even if not realtime.

Test strategy: contract test in `tests/asr/test_whisper_provider.py` runs against a real ~3-second Chinese WAV fixture; asserts `TranscriptChunk` shape (non-empty text, `asr_provider_used == "whisper"`, ended_at > started_at). Test is slow (~10–30s for first model load + transcription) but only runs once because of `pytest_asyncio` and module-scope fixture for the provider.

### AudioCaptureService shape

`packages/backend/meeting_playbook/audio/capture.py` — single class `AudioCaptureService` with this lifecycle:

```python
async with AudioCaptureService(
    meeting_id="m_abc",
    recordings_dir=Path("~/MeetingPlaybook/recordings").expanduser(),
    chunk_seconds=10.0,
    silence_warning_after=30.0,
) as session:
    async for event in session.events():
        # event is one of: AudioChunk, SilenceWarning, CaptureError
        ...
# On exit: WAV file finalized at {recordings_dir}/{meeting_id}/me.wav
```

Internals:
- `sounddevice.RawInputStream` with default device, callback writes raw bytes into an `asyncio.Queue` (the audio thread is sync, but the queue is async-safe via `loop.call_soon_threadsafe`).
- A consumer task drains the queue every `chunk_seconds`, packages the bytes into an `AudioChunk` event, and also accumulates them into an in-memory buffer.
- A separate silence-watch task computes RMS over a sliding window; emits `SilenceWarning` if RMS < threshold for `silence_warning_after`.
- On context-manager exit, the entire buffer is written to `me.wav` (16kHz mono int16) atomically (`.tmp` → rename).
- Device discovery: defaults to `sounddevice.default.device[0]`; logs the chosen device name on start.

Why context manager + async iterator: pairs naturally with the WS handler that wants to forward events 1:1 to the browser. Failures (device unplugged, permission denied) raise typed exceptions that the WS handler maps to `error` frames.

Tests: `tests/audio/test_capture.py` is gated by `pytest.mark.skipif(not _has_audio_input())` — runs locally on Sean's M3 Pro, skipped on CI.

### WebSocket endpoint design

`GET /api/meetings/{id}/session` upgrades to WebSocket. Lives in `packages/backend/meeting_playbook/sessions/router.py`. Flow:

1. Auth — read `X-User-Id` from gateway. Without it, reject with HTTP 401 + `auth.gateway_bypass` BEFORE upgrade.
2. Ownership — `MeetingRepository.get_for_user(user_id, meeting_id)`. Missing → 404 + `meeting.not_found` (no leak).
3. Upgrade — accept WS.
4. Wait for first client message — MUST be `{type: "start_meeting", meeting_id}` with id matching path. Mismatch → send `{type: "error", error_code: "session.bad_start"}` then close.
5. `MeetingRepository.transition_status(meeting_id, "scheduled", "in_progress")`. If status was already past `scheduled` (someone re-opened a tab on a completed meeting) → send `{type: "error", error_code: "session.bad_status"}` and close.
6. Open `AudioCaptureService` via `async with`. Spawn ASR consumer.
7. Send `{type: "meeting_started", meeting_id}` to client.
8. Loop: for each `AudioChunk` from capture, transcribe via `ASRProvider`, persist via `SessionRepository.insert_chunk(...)`, send `{type: "transcript_chunk", ...}` to client.
9. Forward `SilenceWarning` events as `{type: "silence_warning", since}`.
10. End of session triggered by EITHER client `end_meeting` message OR client disconnect (CloseEvent OR exception). Either path: stop capture, finalize WAV (handled by capture service exit), `MeetingRepository.transition_status("in_progress", "completed")`, persist `recording` row, send `{type: "meeting_ended"}` if WS still open, close.

Concurrency: one async task pulls from capture, ONE serial pipeline transcribes + persists + broadcasts. We do NOT parallelize transcription — keeping ordering simple is more important than throughput for this slice.

### WS message contract — Pydantic models

`packages/backend/meeting_playbook/sessions/messages.py` defines tagged-union models for both directions. Each has `type: Literal[...]`. Server uses a discriminated union for client messages so unknown types raise validation errors immediately.

The contract is documented in the spec (`meeting-session/spec.md`) with example matrices per message type. Frontend `lib/session-ws.ts` mirrors the same shapes as TypeScript types.

### Status transitions on `meeting`

`MeetingRepository.transition_status(meeting_id, expected_from, target)`:
- Atomic `UPDATE meeting SET status = :target, updated_at = now() WHERE id = :id AND status = :expected_from RETURNING id`
- If `RETURNING` is empty → either meeting doesn't exist OR status was wrong; raise `MeetingStatusConflict("expected from=X, was actually Y or row missing")`.
- Used only by sessions router; not exposed on public REST.
- Allowed transitions: `scheduled → in_progress`, `in_progress → completed`. Anything else raises.

### React `useMeetingSession` hook

`packages/web/src/hooks/use-meeting-session.ts`:

```ts
type SessionState =
  | { phase: "idle" }
  | { phase: "connecting" }
  | { phase: "in_progress"; chunks: TranscriptChunk[]; silenceSince: string | null }
  | { phase: "ended"; chunks: TranscriptChunk[] }
  | { phase: "error"; errorCode: string; chunks: TranscriptChunk[] };

function useMeetingSession(meetingId: string): {
  state: SessionState;
  start(): void;
  end(): void;
};
```

Internals: `useReducer` keyed by inbound WS message type. WS instance held in `useRef`, lifecycle (open / message / error / close) dispatches reducer actions. `start()` opens the WS and sends `start_meeting`; `end()` sends `end_meeting` and closes. On unmount: closes WS without sending `end_meeting` (defensive — sessions router treats client-close as end-of-session).

Reconnect: ONE retry attempt with 1s backoff if WS closes unexpectedly during `in_progress`. Fails → state enters `error`. No replay of missed chunks (out of scope per Issue #8).

Tests: `tests/hooks/use-meeting-session.test.tsx` — `act` + custom mock WebSocket class. Asserts every state transition (idle → connecting → in_progress; transcript_chunk appends; silence_warning sets silenceSince; end_meeting triggers ended; error message → error state).

### React `TranscriptPane` + capture indicator

`packages/web/src/components/transcript-pane.tsx` — pure component, takes `chunks: TranscriptChunk[]` + `meDisplayName: string`. Renders chronologically; each chunk shows speaker name (always `meDisplayName` for slice-6) + start time + text. Uses CSS gap + flex; styling mirrors slice-04 PlaybookPane card aesthetic. NO emoji per Sean's UI feedback (slice-05 ingest).

`packages/web/src/components/capture-indicator.tsx` — tiny component: pulsing dot (CSS animation) + label `"擷取中" / "Capturing"`; goes to a warning style when `silenceSince` is non-null.

Detail page (`routes/meetings/detail.tsx`) wires it up. Start / End buttons disable based on state. PlaybookPane (slice-04) stays where it is; transcript appears below or beside it (defer the precise layout decision to the Slice 6 propose discussion that the existing memory entry `project_meeting_detail_layout_open.md` flagged — for now, stack vertically: meeting card → playbook → transcript pane → capture indicator).

### Bun gateway WebSocket upgrade

The existing gateway code already detects `Upgrade: websocket` and forwards via `fetch` (per the slice-01 contract that specifies WebSocket upgrade carries `X-User-Id`). This slice formalizes the contract:

- `auth-gateway-contract` MODIFIED: add a Requirement that explicitly covers WS upgrade — gateway MUST authenticate before upgrade (auth check happens in same path as non-WS), MUST inject `X-User-Id` + `X-User-Name` + `X-User-Email` on the upgrade request, MUST close upstream when downstream client closes.
- New test `packages/auth/src/__tests__/gateway-websocket.test.ts` asserts headers are injected on upgrade.

If actual upgrade behavior diverges from current `fetch + duplex: half` (Bun-specific) — pivot to Bun's native WebSocket upgrade API and document.

### Test strategy (TDD vertical slice)

- **Backend pytest:**
  - `tests/asr/test_whisper_provider.py` — ASRProvider contract test; transcribes real ~3s WAV fixture; one fixture file (`tests/asr/fixtures/short_speech_zh.wav`)
  - `tests/audio/test_capture.py` — device-guarded integration test; skipif no input device
  - `tests/sessions/test_repository.py` — transcript_chunk + recording inserts
  - `tests/sessions/test_service.py` — orchestration with mock ASRProvider + mock AudioCaptureService; asserts ordering + persistence + WS frame shape
  - `tests/sessions/test_router.py` — WS endpoint integration with `httpx.AsyncClient` WebSocket support; asserts ownership gate, status transitions, full message sequence (start_meeting → meeting_started → 2× transcript_chunk → end_meeting → meeting_ended), error frames on bad start
  - `tests/meetings/test_repository.py` — extend with `transition_status` allowed / forbidden cases
- **Frontend bun test:**
  - `lib/session-ws.test.ts` — WS client wrapper open / send / close / parse error
  - `hooks/use-meeting-session.test.tsx` — every reducer state transition with mocked WebSocket
  - `components/transcript-pane.test.tsx` — renders chunks chronologically with meDisplayName
  - `components/capture-indicator.test.tsx` — idle / active / silence-warning visual states
  - `routes/meetings/detail.test.tsx` — Start button opens session, transcript appears, End button closes
- **Auth gateway bun test:**
  - `__tests__/gateway-websocket.test.ts` — WS upgrade carries identity headers

## Risks / Trade-offs

- [Risk] **faster-whisper large-v3-turbo on M3 Pro CPU may not run realtime** — chunks could pile up, latency drifts. Mitigation: 10s chunk gives ~3-5s headroom; if drift observed in smoke test, document as known issue and let user pick `WHISPER_MODEL_SIZE=small` env override.
- [Risk] **Bun gateway WebSocket forwarding via fetch + duplex: half** — Bun supports this but it's not the canonical "Bun.serve websocket" API; some edge cases (binary frames, ping/pong) may differ. Mitigation: spike during the gateway WS test task; if broken, switch to Bun.serve's `websocket: { open, message, close }` handler and proxy at frame layer.
- [Risk] **macOS microphone permission denied on first run** — `sounddevice` raises `PortAudioError` mid-stream. Mitigation: pre-flight check on session start (`sounddevice.query_devices()`) → if no input device available raise `CaptureDeviceUnavailable` → router maps to `{error_code: "session.no_audio_device"}`; document permission-grant steps in README.
- [Risk] **WAV writer holds entire session in memory** — a 1-hour meeting is ~115MB at 16kHz mono int16; acceptable for slice-6 single-user dev but not for prod or long sessions. Mitigation: documented Trade-off; switch to streaming WAV writer (`soundfile.SoundFile` open mode) is a 1-task follow-up.
- [Risk] **Tab close mid-session leaves DB row stuck at `in_progress`** — server detects WS close and transitions to `completed`, but if backend ALSO crashes mid-session the row stays `in_progress`. Mitigation: out of scope for slice-6; future slice can add a "stuck-session reconciler" cron.
- [Risk] **One serial transcription pipeline becomes the bottleneck** — if transcription is slower than capture, queue grows unbounded. Mitigation: bound the audio queue at `chunk_seconds * 6` (60s of audio); if full, drop oldest with a warning frame `session.queue_overflow`. Spec'd in router.
- [Risk] **WhisperProvider model load time blocks the first transcript_chunk** — first call loads the model (~10s) BEFORE first transcription, so user sees "Capturing..." with no chunks for 15-25s on first run after backend restart. Mitigation: documented; future enhancement could pre-warm the model on FastAPI startup.
- [Trade-off] **Choosing `transcript_chunk.speaker` as a free string column instead of an enum** — slice-7 needs `"counterparty"`, slice-12 might need `"system"` for VibeVoice diarization. Free string + check constraint `IN ('me', 'counterparty', 'system')` is more flexible than a Postgres ENUM that requires a migration to extend.

## Migration Plan

1. Alembic migration `0003_create_session_tables.py` creates `transcript_chunk` + `recording` tables. Both have FK to `meeting.id` ON DELETE CASCADE.
2. `pyproject.toml` adds `faster-whisper`, `sounddevice`, `numpy` (numpy is transitive but pin minimum).
3. `.env.example` adds the 4 new env vars; README documents `RECORDINGS_DIR` defaults to `~/MeetingPlaybook/recordings`.
4. First-run README note: "Whisper will download the large-v3-turbo model (~1.5GB) on first transcription; allow 1-2 minutes."
5. Rollback: `alembic downgrade -1` drops the two tables. WAV files on disk are NOT cleaned up (defer to slice-13 cleanup).

## Open Questions

- Detail page layout — already flagged in `project_meeting_detail_layout_open.md` memory; for slice-6 stack vertically (meeting card → playbook → transcript), revisit when Slice 7 / 8 add more in-meeting surface.
- Recording dir creation — should the server create `RECORDINGS_DIR` if it doesn't exist? Decision: yes, `mkdir -p` lazily on first session start; permission errors raise `CaptureDeviceUnavailable`.
- Whisper compute device fallback — if user has CUDA but it fails to init, should we fall back to CPU? Decision: yes, log warning, continue on CPU; documented in design.
- WS reconnect strategy — single retry with 1s backoff, then surface error. More aggressive reconnect (with chunk replay) is out of scope.
