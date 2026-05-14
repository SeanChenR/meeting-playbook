# ADR-0029: Hybrid speaker attribution — binary for dual-channel, pyannote-driven diarization for single-channel

- **Status**: Accepted
- **Date**: 2026-05-14
- **Decider**: Sean
- **Amends**: ADR-0016 (binary speaker labels with per-meeting custom display names)

## Context

ADR-0016 chose binary speaker tagging (`me` / `counterparty`) because `Dual-channel capture` (ADR-0004) gives speaker identity at the source — BlackHole → counterparty, microphone → me. That design is correct for online meetings where the user has BlackHole installed and routes the remote audio through it.

Face-to-face meetings break this assumption. With only a single laptop microphone running, there is no per-stream source tag — every voice in the room lands on the same audio track. ADR-0016's binary attribution cannot work in that configuration, leaving the entire transcript without speaker labels. v1.1's slice 12 fills this gap.

Two questions to settle:
1. Should the existing dual-channel path be replaced or extended?
2. What concrete diarization engine fills the single-channel gap?

## Decision

**(1) Extend, not replace.** Introduce a `SpeakerAttributionStrategy` abstraction at the session-finalize boundary:

- `DualChannelStrategy` — preserves ADR-0016. The dual-channel ASR pipeline still writes `speaker = "me"` (mic) or `"counterparty"` (BlackHole) at chunk insertion time; the strategy validates the pair and passes chunks through immutably.
- `SingleChannelStrategy` — for `Single-channel mode (面對面模式)`. Runs `DiarizationProvider.diarize(...)` once for the lone Recording, then maps each chunk to a `speaker_cluster_{N}` label by largest-overlap segment match.

A `select_strategy(recordings)` selector dispatches based on the recording configuration: two recordings with streams `{me, counterparty}` → dual; one recording → single; anything else → `InvalidSpeakerConfiguration`.

**(2) `pyannote.audio` is the sole v1.1 diarization provider.** Use `pyannote/speaker-diarization-3.1` via HuggingFace Hub, gated on `PYANNOTE_AUTH_TOKEN`. No fallback provider in v1.1: when the token is missing, `select_strategy` raises `DiarizationProviderUnavailable` and the single-channel session aborts with `session.invalid_speaker_configuration` rather than producing degraded output.

ADR-0016 remains in force for dual-channel sessions; this ADR layers a new mode on top, does not supersede it.

## Consequences

- **Schema unchanged.** `transcript_chunk.speaker` is already `TEXT`; the value space expands to include `speaker_cluster_{N}` (1-based) and `speaker_cluster_unknown`. No migration required.
- **Recording stream values unchanged.** `Recording.stream` continues to use the existing `{me, counterparty}` vocabulary from slice 6/7. Single-channel meetings have a single Recording with `stream = "me"` (the user's mic).
- **WebSocket contract widens.** `transcript_chunk` server frames may now carry `speaker = "speaker_cluster_<N>"` or `"speaker_cluster_unknown"` in addition to `"me"` / `"counterparty"`. The meeting-session spec reflects this.
- **First single-channel meeting downloads ~300MB.** pyannote pulls the diarization pipeline + dependency models from HuggingFace on first `diarize(...)` call. Subsequent meetings reuse the cache.
- **New required env var.** `PYANNOTE_AUTH_TOKEN` is required for `Single-channel mode`. The user must accept the gating terms at `huggingface.co/pyannote/speaker-diarization-3.1` and `huggingface.co/pyannote/segmentation-3.0`.
- **Rollback path exists.** `SPEAKER_HYBRID_ENABLED=false` forces `select_strategy` to accept only dual-channel configurations and reject single-channel as invalid, restoring strictly the pre-slice-12 behaviour.
- **No cluster persistence across meetings.** A speaker labelled `speaker_cluster_2` in meeting A is unrelated to `speaker_cluster_2` in meeting B. Cross-meeting speaker identification is explicitly out of scope (per CONTEXT.md non-goals).

## Alternatives considered

- **`AppleSpeechProvider` via macOS Speech Framework** — initially planned as an offline / no-network fallback. **Rejected** after implementation review: the Speech framework provides speech recognition (ASR), not speaker diarization. The closest macOS-native option, `SoundAnalysis`, only classifies sound types (speech / music / noise) and cannot separate speakers. Wiring it up would silently emit single-cluster output and masquerade as diarization, which is worse than a loud "unavailable" error.
- **Third-party fallback such as `simple-diarizer` or `pyAudioAnalysis`** — deferred to a future ADR. Adding a second backend in v1.1 doubles the surface area without an established quality bar; pyannote-only is the simpler v1.1.
- **Cloud diarization providers (Google Speech `enable_speaker_diarization`, AssemblyAI)** — deferred. Cloud providers add cost and network coupling; pyannote running locally on the M3 Pro is consistent with `CONTEXT.md`'s "local-first" boundary. A future ADR may add cloud providers behind the same `DiarizationProvider` interface.
- **Inline `if recording_count == 1` branch in `runtime`** — rejected. The strategy abstraction keeps `runtime` decoupled from diarization concerns and mirrors the existing `ASRProvider` pattern (ADR-0005), which has paid off as new ASR engines were added.
- **Reuse the `chunk.speaker` field as a stream tag for both modes** — rejected. The single-channel strategy overwrites the placeholder `"me"` value with `speaker_cluster_{N}`; this is fine in isolation, but using the same field as both "raw stream" and "final attribution" would muddy the contract for future diarization providers.

## Future work

- Add a second `DiarizationProvider` impl (cloud or local) once v1.1 use shows pyannote's weaknesses concretely. ADR will reference quantitative gaps, not speculation.
- Cross-meeting speaker identity via the slice 13 `VoiceEnrollmentMatcher`: when an enrolled voice is available, `SingleChannelStrategy` will auto-name one of the clusters `me` instead of leaving it as `speaker_cluster_N`. Out of scope for slice 12.
