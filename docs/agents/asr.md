# ASR (Automatic Speech Recognition) — agent notes

> Slice 6 (`slice-06-mic-transcript-session`) outcome.
> Module: `packages/backend/meeting_playbook/asr/`.
> See ADR-0005 for the pluggable-provider rationale.

## ASRProvider Protocol

`meeting_playbook.asr.base.ASRProvider` is the only contract that ASR-using
code (the session orchestrator) depends on. Adding a new engine
(VibeVoice in Slice 12, AssemblyAI in some hypothetical future slice, etc.)
is a drop-in by implementing the Protocol — no changes to
`AudioCaptureService` or the WebSocket router are required.

```python
@runtime_checkable
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

Returns a `TranscriptChunk(text, started_at, ended_at, asr_provider_used,
confidence)`. Both `started_at` and `ended_at` MUST be timezone-aware UTC.

### Why the contract looks like this

- **Bytes in, dataclass out** — keeps the interface decoupled from numpy /
  soundfile / specific in-memory shapes. Provider implementations convert
  as needed (Whisper takes float32 numpy; VibeVoice may want raw PCM).
- **Async** — even sync providers (faster-whisper is sync) wrap the call
  in `asyncio.to_thread` so the WebSocket event loop stays unblocked.
- **`sample_rate_hz` explicit** — providers MUST NOT assume 16kHz. The
  capture service knows the truth and passes it down.
- **`language_hint` optional** — Whisper auto-detects; for `zh-TW` we pass
  `"zh"` to nudge it. Other providers may use it differently.
- **`confidence`** is `float | None` because not all providers expose it
  cleanly. When non-null it MUST be in 0..1.

## Lazy-load pattern

Provider constructors store config but DO NOT load models. First
`transcribe_chunk` call instantiates the heavy state (Whisper's
`WhisperModel` is ~1.5GB and downloaded on first run); subsequent calls
reuse it via instance state. This keeps:
- Process startup fast (no 10-second model load on FastAPI boot)
- Tests fast (provider construction is free; only the slow contract test
  pays the model-load cost, and it's module-scope-cached)
- Capture-side `AudioChunk` arriving before model is loaded gracefully
  blocks on first transcription rather than failing

## Drop-in invariant test

`tests/asr/test_whisper_provider.py` must remain the canonical contract
test. When adding a new provider:
1. Implement the Protocol
2. Add `tests/asr/test_<provider>_provider.py` mirroring the Whisper test
   shape — same fixture, same assertions
3. Do NOT modify the session router or AudioCaptureService

The session router includes a static-analysis test that greps the router
source for non-Whisper provider imports — a future second provider must
NOT be imported by the router. Wire it via the
`get_asr_provider_dependency` FastAPI dependency override.

## Configuration

| Env var                  | Default              | Notes                                                                                        |
| ------------------------ | -------------------- | -------------------------------------------------------------------------------------------- |
| `WHISPER_MODEL_SIZE`     | `large-v3-turbo`     | Drop to `small` or `tiny` for faster CPU runs at the cost of accuracy                        |
| `WHISPER_DEVICE`         | `auto`               | `cpu` / `cuda` / `auto`. M-series Macs run on CPU; CUDA path untested in this slice          |
| `WHISPER_COMPUTE_TYPE`   | `auto`               | `int8` is the realistic CPU default; `float16` for GPU                                       |

faster-whisper downloads models from HuggingFace Hub on first call; the
download cache lives at `~/.cache/huggingface/`. First-run download for
`large-v3-turbo` is ~1.5GB and takes 1–2 minutes on a good connection.
