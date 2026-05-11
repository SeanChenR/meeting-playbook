## ADDED Requirements

### Requirement: WebSocket connect resolves ASR providers via factory using meeting.asr_provider

The WS endpoint handler at `packages/backend/meeting_playbook/sessions/ws.py` (the `meeting_session_ws` route from slice-7) SHALL replace its current FastAPI `Depends(get_whisper_singleton_*)` dependency injection with a runtime call to `get_asr_providers_for_meeting(meeting.asr_provider)` from `packages/backend/meeting_playbook/asr/factory.py`. The call SHALL happen ONCE per WS connection, after the meeting row is loaded but before any audio frames are accepted.

The factory return value SHALL be a tuple `(me_provider: ASRProvider, counterparty_provider: ASRProvider)` — two independent provider instances so per-stream state (warmup status, sample-rate cache) does not leak across streams. The handler SHALL use these provider instances throughout the session lifetime; no second factory call SHALL fire for the same connection.

If the factory returns `None` providers (defensive — the fallback path means this SHALL NOT occur in practice), the handler SHALL close the WebSocket with code `1011` and an envelope `{error_code: "session.asr_unavailable", message: ...}`. This case is reserved for future providers that fail at construction time (e.g., model missing on disk).

#### Scenario: Connect to a qwen3-flagged meeting wires Qwen3 providers

- **GIVEN** a meeting with `asr_provider = "qwen3"`
- **WHEN** the client opens a WS connection to `/api/meetings/{id}/session`
- **THEN** the handler SHALL call `get_asr_providers_for_meeting("qwen3")` exactly once; the returned providers SHALL both be instances of `Qwen3ASRProvider`; the WS SHALL accept frames normally

#### Scenario: Connect to a whisper-flagged meeting wires Whisper providers

- **GIVEN** a meeting with `asr_provider = "whisper"`
- **WHEN** the client opens a WS connection
- **THEN** the handler SHALL call `get_asr_providers_for_meeting("whisper")` exactly once; the returned providers SHALL both be instances of `WhisperASRProvider`; the WS SHALL accept frames normally

#### Scenario: Connect to an unknown asr_provider value falls back to Whisper

- **GIVEN** a meeting whose `asr_provider` was somehow set to `"experimental_xyz"` (legacy value or admin override)
- **WHEN** the client opens a WS connection
- **THEN** the factory SHALL log a warning `unknown asr_provider 'experimental_xyz', falling back to whisper`; the providers SHALL be `WhisperASRProvider` instances; the WS SHALL accept frames normally

#### Scenario: Existing WS contract from slice-7..10 is preserved (no message-shape changes)

- **GIVEN** a connected WS session
- **WHEN** the client sends `audio_chunk_me` / `audio_chunk_counterparty` frames at 100ms cadence
- **THEN** the handler SHALL invoke the resolved provider's `transcribe_chunk` exactly as before; outgoing `transcript_chunk_me` / `transcript_chunk_counterparty` frames SHALL retain their slice-7 shape (`{type, started_at, ended_at, text}`) — slice-11 introduces NO changes to wire-level frame names or fields

### Requirement: Switching meeting.asr_provider mid-session has no effect on the live WS

A user switching the AsrProviderSelector dropdown (slice-11 detail-page UI) issues a PUT to `/api/meetings/{id}` that updates `meeting.asr_provider`. The WS session for that same meeting SHALL NOT pick up the change while still connected — the providers resolved at WS connect time SHALL remain in use until the WS closes. The new value takes effect on the NEXT WS connect (typically the user's next meeting).

This intentionally avoids tearing down the live providers mid-meeting (would drop in-flight chunks) and matches the AsrProviderSelector hint "切換下一場會議生效" / "Takes effect on the next meeting" (see meeting-detail-layout delta).

#### Scenario: Mid-session provider switch is ignored by the live WS

- **GIVEN** an active WS session for a meeting whose connect-time `asr_provider` was `"whisper"` (so both providers are WhisperASRProvider instances)
- **WHEN** the user PUTs `/api/meetings/{id}` with `{asr_provider: "qwen3"}` while the WS is still open
- **THEN** the persisted row SHALL update to `qwen3`; the live WS session SHALL continue using the WhisperASRProvider instances; subsequent `audio_chunk_*` frames SHALL still be transcribed by Whisper

#### Scenario: Reconnecting after a switch picks up the new provider

- **GIVEN** the previous scenario's switched-but-still-using-whisper session
- **WHEN** the WS closes and the user reconnects
- **THEN** the factory SHALL be called again; the returned providers SHALL be `Qwen3ASRProvider` instances reflecting the new `asr_provider = "qwen3"`
