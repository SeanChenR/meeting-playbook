# speaker-attribution-strategy Specification

## Purpose

Assigns a `speaker` value to every `transcript_chunk` at session-finalize
time, decoupling the rule "which speaker said this chunk" from the audio
capture pipeline. Two strategies coexist: `DualChannelStrategy` validates
the binary `me` / `counterparty` labels the dual-channel ASR pipeline
already produced, while `SingleChannelStrategy` runs a `DiarizationProvider`
over a single-mic recording and tags each chunk with
`speaker_cluster_<N>`. `select_strategy(recordings)` is the single entry
point that picks the right strategy from the recording configuration.

v1.1 ships exactly one diarization provider — `PyannoteProvider`, backed
by `pyannote/speaker-diarization-3.1` on HuggingFace Hub. The hybrid
attribution layer is gated by `SPEAKER_HYBRID_ENABLED` (default true) so
the dual-channel-only path can be restored quickly if pyannote outputs
degrade in production. See ADR-0029 for the full rationale and the
deferred cloud-provider / Apple Speech alternatives.

## Requirements

### Requirement: SpeakerAttributionStrategy interface assigns speaker labels to transcript chunks

The backend SHALL provide a `SpeakerAttributionStrategy` Abstract Base Class at `packages/backend/meeting_playbook/speaker/strategy.py` with a single method `assign_speakers(recordings: list[Recording], chunks: list[TranscriptChunk]) -> list[TranscriptChunk]`. Implementations MUST return new `TranscriptChunk` instances (or copies) with the `speaker` field populated; they MUST NOT mutate the input list or any input instances. The returned list SHALL contain exactly one output chunk per input chunk, preserving order.

#### Scenario: assign_speakers preserves count and order

- **GIVEN** a strategy implementation and an input list of three `TranscriptChunk` instances ordered by `started_at`
- **WHEN** `assign_speakers(recordings, chunks)` runs
- **THEN** the returned list SHALL contain exactly three chunks in the same `started_at` order

#### Scenario: assign_speakers does not mutate input chunks

- **GIVEN** an input chunk whose `speaker` field equals `"unassigned"` before the call
- **WHEN** any `SpeakerAttributionStrategy` impl processes it
- **THEN** the original input chunk's `speaker` field SHALL still equal `"unassigned"` after the call

### Requirement: DualChannelStrategy validates pre-labeled binary speaker values from the dual-channel ASR pipeline

The backend SHALL provide a `DualChannelStrategy` implementation of `SpeakerAttributionStrategy`. The dual-channel ASR pipeline (existing slice-6 / slice-7 behavior) MUST write `chunk.speaker = "me"` for microphone-sourced chunks and `chunk.speaker = "counterparty"` for BlackHole-sourced chunks BEFORE this strategy is invoked. `DualChannelStrategy.assign_speakers(recordings, chunks)` SHALL therefore return new `TranscriptChunk` instances whose `speaker` field equals the input chunk's `speaker` value, provided that value is exactly `"me"` or `"counterparty"`. Any input chunk whose `speaker` is neither `"me"` nor `"counterparty"` SHALL cause the strategy to raise `UnresolvableChunkStream` carrying the offending chunk id; the strategy MUST NOT silently default to a placeholder. The strategy MUST NOT mutate the input chunks (per the `SpeakerAttributionStrategy` immutability rule). The `recordings` parameter is unused by `DualChannelStrategy` (recording-set validation happens at `select_strategy` time).

#### Scenario: me-labeled chunks pass through unchanged with a new instance returned

- **GIVEN** two `Recording` rows for one meeting with `stream = "me"` and `stream = "counterparty"`, and one input chunk whose `speaker` field already equals `"me"`
- **WHEN** `DualChannelStrategy.assign_speakers(recordings, [chunk])` runs
- **THEN** the returned chunk's `speaker` field SHALL equal `"me"` AND the returned chunk SHALL NOT be the same Python object as the input chunk

#### Scenario: counterparty-labeled chunks pass through unchanged with a new instance returned

- **GIVEN** the same two `Recording` rows and one input chunk whose `speaker` field already equals `"counterparty"`
- **WHEN** `DualChannelStrategy.assign_speakers(recordings, [chunk])` runs
- **THEN** the returned chunk's `speaker` field SHALL equal `"counterparty"` AND the returned chunk SHALL NOT be the same Python object as the input chunk

#### Scenario: chunk with unexpected speaker value raises UnresolvableChunkStream

- **GIVEN** an input chunk whose `speaker` field equals `"speaker_cluster_1"` (a value produced only by `SingleChannelStrategy`, not by the dual-channel pipeline)
- **WHEN** `DualChannelStrategy.assign_speakers(recordings, [chunk])` runs
- **THEN** the call SHALL raise `UnresolvableChunkStream` whose message references the offending chunk id and value

### Requirement: SingleChannelStrategy assigns speaker_cluster_N labels via DiarizationProvider

The backend SHALL provide a `SingleChannelStrategy(provider: DiarizationProvider, overlap_threshold_ms: int = 250)` implementation of `SpeakerAttributionStrategy`. On `assign_speakers(recordings, chunks)` it SHALL invoke `provider.diarize(recordings[0].file_path)` once for the single recording and obtain a list of `DiarizationSegment(start_ms, end_ms, cluster_id)` values. For each input chunk, the strategy SHALL select the segment whose temporal overlap with the chunk window (`started_at`..`ended_at` relative to `recording.started_at`) is the largest; that segment's `cluster_id` (a 1-based integer) SHALL be rendered as the string `speaker_cluster_{cluster_id}` and written into the returned chunk's `speaker` field. If no segment overlaps a given chunk by at least `overlap_threshold_ms`, the chunk's `speaker` SHALL be set to `"speaker_cluster_unknown"`.

#### Scenario: chunk labeled by largest-overlap diarization segment

- **GIVEN** a single recording with diarization segments `[(0, 5000, 1), (5000, 10000, 2)]` (ms) and one input chunk spanning 4500–5500ms relative to the recording's `started_at`
- **WHEN** `SingleChannelStrategy(...).assign_speakers([recording], [chunk])` runs
- **THEN** the returned chunk's `speaker` SHALL equal `"speaker_cluster_2"` (the 5000–10000ms segment overlaps the chunk by 500ms while the 0–5000ms segment overlaps it by 500ms; ties resolve to the later segment)

#### Scenario: chunk with no overlapping segment falls back to unknown label

- **GIVEN** a single recording with diarization segments `[(0, 5000, 1)]` and a chunk spanning 10000–11000ms
- **WHEN** `SingleChannelStrategy(...).assign_speakers([recording], [chunk])` runs
- **THEN** the returned chunk's `speaker` SHALL equal `"speaker_cluster_unknown"`

### Requirement: DiarizationProvider interface exposes diarize for single-channel audio

The backend SHALL provide a `DiarizationProvider` Abstract Base Class at `packages/backend/meeting_playbook/speaker/diarization.py` exposing `diarize(wav_path: Path) -> list[DiarizationSegment]` where `DiarizationSegment` is a frozen dataclass with `start_ms: int`, `end_ms: int`, and `cluster_id: int` (1-based). Implementations SHALL return segments ordered by `start_ms`, with no overlapping segments. Inputs SHALL be 16kHz mono WAV files; behavior on other formats is unspecified (callers normalize before invocation).

#### Scenario: diarize returns ordered non-overlapping segments

- **GIVEN** any `DiarizationProvider` implementation and a 16kHz mono WAV containing two speakers
- **WHEN** `provider.diarize(wav_path)` runs
- **THEN** the returned list SHALL be non-empty, each segment's `end_ms` SHALL exceed its `start_ms`, segments SHALL be sorted by `start_ms` ascending, and consecutive segments SHALL satisfy `segments[i].end_ms <= segments[i+1].start_ms`

### Requirement: PyannoteProvider implements DiarizationProvider via HuggingFace pretrained model

The backend SHALL provide a `PyannoteProvider` at `packages/backend/meeting_playbook/speaker/pyannote_provider.py` implementing `DiarizationProvider`. The implementation SHALL lazily load the `pyannote/speaker-diarization-3.1` pipeline from HuggingFace Hub on first `diarize(...)` call using the access token read from the `PYANNOTE_AUTH_TOKEN` environment variable. Subsequent calls SHALL reuse the loaded pipeline. If `PYANNOTE_AUTH_TOKEN` is not set when `diarize(...)` is first invoked, the provider SHALL raise `DiarizationProviderUnavailable` carrying the missing-token message.

#### Scenario: First diarize call loads pipeline; subsequent calls reuse it

- **GIVEN** a freshly constructed `PyannoteProvider` and a valid `PYANNOTE_AUTH_TOKEN`
- **WHEN** `diarize(wav_path)` runs the first time
- **THEN** the pipeline SHALL be loaded (downloaded if not cached) and the call SHALL return a non-empty list of `DiarizationSegment`
- **AND** a second `diarize(...)` call SHALL NOT re-load the pipeline (verified by patching the loader and asserting it is invoked exactly once)

#### Scenario: Missing token raises DiarizationProviderUnavailable

- **GIVEN** a freshly constructed `PyannoteProvider` with `PYANNOTE_AUTH_TOKEN` unset
- **WHEN** `diarize(wav_path)` runs
- **THEN** the call SHALL raise `DiarizationProviderUnavailable` whose message references the missing environment variable

### Requirement: PyannoteProvider is the single DiarizationProvider impl in v1.1

The backend SHALL ship exactly one `DiarizationProvider` implementation in v1.1 (`PyannoteProvider`). v1.1 SHALL NOT include an offline / no-network fallback diarization provider; Apple Speech Framework offers no public speaker-diarization API, and falling back to a `SoundAnalysis`-style speech / non-speech segmenter would silently produce single-cluster results that masquerade as diarization. Future diarization providers (cloud or alternative local engines) SHALL be introduced through a separate ADR + change proposal.

#### Scenario: select_strategy without an injected provider raises when PYANNOTE_AUTH_TOKEN is unset

- **GIVEN** a meeting with exactly one `Recording` row, no `single_channel_provider` argument passed to `select_strategy`, and `PYANNOTE_AUTH_TOKEN` unset in the environment
- **WHEN** `select_strategy(recordings)` runs
- **THEN** the call SHALL raise `DiarizationProviderUnavailable` whose message names the missing `PYANNOTE_AUTH_TOKEN` environment variable; the call SHALL NOT silently substitute a degraded provider

### Requirement: select_strategy chooses dual or single based on recording configuration

The backend SHALL expose `select_strategy(recordings: list[Recording]) -> SpeakerAttributionStrategy` at `packages/backend/meeting_playbook/speaker/strategy.py`. The selector SHALL return a `DualChannelStrategy` instance when the input contains exactly two recordings whose `stream` values are `{"me", "counterparty"}`, and a `SingleChannelStrategy` instance configured with the project's default `DiarizationProvider` when the input contains exactly one recording. Any other configuration (zero recordings, two recordings with mismatched stream names, three or more recordings) SHALL cause `select_strategy(...)` to raise `InvalidSpeakerConfiguration` carrying a description of the offending configuration.

#### Scenario: Two recordings with me+counterparty stream names yield DualChannelStrategy

- **GIVEN** a meeting with two `Recording` rows whose `stream` values are `"me"` and `"counterparty"`
- **WHEN** `select_strategy(recordings)` runs
- **THEN** the returned strategy SHALL be an instance of `DualChannelStrategy`

#### Scenario: Single recording yields SingleChannelStrategy

- **GIVEN** a meeting with exactly one `Recording` row
- **WHEN** `select_strategy(recordings)` runs
- **THEN** the returned strategy SHALL be an instance of `SingleChannelStrategy`

#### Scenario: Mismatched dual stream names raise InvalidSpeakerConfiguration

- **GIVEN** a meeting with two `Recording` rows whose `stream` values are `"me"` and `"me"`
- **WHEN** `select_strategy(recordings)` runs
- **THEN** the call SHALL raise `InvalidSpeakerConfiguration`

#### Scenario: Three recordings raise InvalidSpeakerConfiguration

- **GIVEN** a meeting with three `Recording` rows
- **WHEN** `select_strategy(recordings)` runs
- **THEN** the call SHALL raise `InvalidSpeakerConfiguration`

<!-- @trace
source: slice-12-speaker-hybrid
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/config.py
  - docs/adr/0029-hybrid-speaker-attribution.md
tests:
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_pyannote_real_audio.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
-->
