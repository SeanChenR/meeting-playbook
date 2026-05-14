# voice-enrollment Specification

## Purpose

Lets each user pre-record a one-off 30-second voice sample (Voice enrollment
sample / 聲紋樣本). When a single-channel meeting finalizes, the cluster
whose embedding matches the enrolled sample above threshold is automatically
renamed from `speaker_cluster_<N>` to `me`, removing the per-meeting manual
"which cluster is me" step introduced by `slice-12-speaker-hybrid`. Only one
enrollment exists per user; re-recording replaces it. Voice enrollment is
attribution-only — it is NOT used for authentication, login, or cross-meeting
speaker identification.

## Requirements

### Requirement: voice_enrollment table stores one embedding per user

The backend SHALL provide a `voice_enrollment` table with columns `(user_id TEXT PRIMARY KEY, sample_wav_path TEXT NOT NULL, embedding BYTEA NOT NULL, created_at TIMESTAMPTZ NOT NULL)`. The `user_id` column SHALL reference Better Auth's `user.id` with `ON DELETE CASCADE` so a deleted user's enrollment is automatically removed (preserving the project-wide rule that auth tables own user lifecycle). Re-uploading an enrollment SHALL replace the existing row in-place rather than appending a second row. There SHALL be at most one row per user.

#### Scenario: Re-upload replaces the existing enrollment row

- **GIVEN** user `u_a` has an existing `voice_enrollment` row with `created_at = 2026-05-01T00:00:00Z`
- **WHEN** `VoiceEnrollmentRepository.upsert(user_id="u_a", wav_path=p, embedding=e)` runs with a fresh sample
- **THEN** the row for `u_a` SHALL have the new `wav_path`, `embedding`, and a later `created_at`; the row count for user `u_a` in `voice_enrollment` SHALL remain exactly 1

#### Scenario: Deleting the user cascades to voice_enrollment

- **GIVEN** user `u_a` has a `voice_enrollment` row
- **WHEN** the corresponding `user` row is deleted by Better Auth
- **THEN** the `voice_enrollment` row for `u_a` SHALL be removed by the database CASCADE without manual cleanup


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - packages/backend/meeting_playbook/voice_enrollment/models.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
tests:
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/voice_enrollment/test_repository.py
-->


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: compute_enrollment_embedding rejects samples that do not produce a single-speaker embedding

The backend SHALL provide `compute_enrollment_embedding(wav_path: Path) -> bytes` at `packages/backend/meeting_playbook/voice_enrollment/embedding.py`. The function SHALL feed the WAV into the project's pyannote diarization pipeline, read `DiarizeOutput.speaker_embeddings`, and verify the result contains exactly one speaker embedding. Any of the following SHALL cause the function to raise `InvalidEnrollmentSample`: more than one speaker detected, zero speakers detected, embedding vector containing only zeros (silent / dropped sample), or pyannote loader raising `DiarizationProviderUnavailable`. The returned `bytes` SHALL be the embedding's float32 representation via `numpy.ndarray.tobytes()`.

#### Scenario: Multi-speaker sample is rejected

- **GIVEN** a WAV containing two distinct speakers
- **WHEN** `compute_enrollment_embedding(wav_path)` runs
- **THEN** the call SHALL raise `InvalidEnrollmentSample` whose message mentions the detected speaker count

#### Scenario: Silent sample is rejected

- **GIVEN** a WAV that contains no recognizable speech (returns an all-zero embedding from the pipeline)
- **WHEN** `compute_enrollment_embedding(wav_path)` runs
- **THEN** the call SHALL raise `InvalidEnrollmentSample` whose message indicates the embedding was empty / zero

#### Scenario: Valid single-speaker sample returns float32 bytes

- **GIVEN** a 30-second WAV of one speaker talking continuously
- **WHEN** `compute_enrollment_embedding(wav_path)` runs
- **THEN** the call SHALL return non-empty `bytes` whose length is divisible by 4 (float32 = 4 bytes per element) and whose first 4 bytes are NOT `\x00\x00\x00\x00`


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
tests:
  - packages/backend/tests/voice_enrollment/test_embedding.py
-->


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: VoiceEnrollmentMatcher picks the highest-similarity cluster above threshold

The backend SHALL provide `VoiceEnrollmentMatcher.find_me_cluster(enrolled_embedding: bytes, cluster_embeddings: dict[int, np.ndarray], threshold: float = 0.5) -> int | None` at `packages/backend/meeting_playbook/voice_enrollment/matcher.py`. The matcher SHALL compute cosine similarity between the enrolled embedding and each cluster's embedding, return the `cluster_id` whose similarity is the highest AND meets `>= threshold`, and return `None` when the best similarity falls below the threshold or when `cluster_embeddings` is empty. The matcher MUST NOT modify either input.

#### Scenario: Highest-similarity cluster above threshold is returned

- **GIVEN** an enrolled embedding `e_me`, three cluster embeddings with cosine similarities to `e_me` of `0.42`, `0.65`, `0.58`, and `threshold = 0.5`
- **WHEN** `find_me_cluster(e_me, {1: c1, 2: c2, 3: c3}, threshold=0.5)` runs
- **THEN** the call SHALL return `2` (the highest similarity above threshold)

#### Scenario: All similarities below threshold returns None

- **GIVEN** an enrolled embedding `e_me` and cluster embeddings whose similarities are all `< 0.5`
- **WHEN** `find_me_cluster(e_me, clusters, threshold=0.5)` runs
- **THEN** the call SHALL return `None`

#### Scenario: Empty cluster set returns None

- **GIVEN** an enrolled embedding `e_me` and `cluster_embeddings = {}`
- **WHEN** `find_me_cluster(e_me, {}, threshold=0.5)` runs
- **THEN** the call SHALL return `None`


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
tests:
  - packages/backend/tests/voice_enrollment/test_matcher.py
-->


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: POST /api/voice_enrollment uploads + replaces the per-user enrollment

The backend SHALL expose `POST /api/voice_enrollment` accepting `multipart/form-data` with a single audio file field. The endpoint SHALL accept only `audio/wav` (16kHz mono PCM) up to 5MB and a duration of 30 seconds or less; non-conforming uploads SHALL be rejected with HTTP 422 and one of the error codes `voice_enrollment.unsupported_format`, `voice_enrollment.too_large`, or `voice_enrollment.too_long`. On a conforming upload the endpoint SHALL persist the WAV under `VOICE_ENROLLMENT_DIR/{user_id}.wav`, run `compute_enrollment_embedding` on the file, upsert the `voice_enrollment` row, and return HTTP 200 with body `{"enrolled_at": "<iso8601>"}`. A failed `compute_enrollment_embedding` (any `InvalidEnrollmentSample`) SHALL surface as HTTP 422 `voice_enrollment.invalid_sample` with the underlying message, AND the WAV file SHALL be removed from disk so partial uploads do not accumulate.

#### Scenario: Valid 30-second WAV from a single speaker enrolls successfully

- **GIVEN** an authenticated user `u_a` with no existing enrollment, and a 25-second 16kHz mono WAV file
- **WHEN** the user POSTs the file to `/api/voice_enrollment`
- **THEN** the response SHALL be HTTP 200 with `enrolled_at` populated, the row in `voice_enrollment` for `u_a` SHALL exist, the WAV file SHALL exist at `VOICE_ENROLLMENT_DIR/u_a.wav`, AND the row's `embedding` length SHALL be divisible by 4

#### Scenario: Re-enrollment overwrites the existing row and WAV

- **GIVEN** user `u_a` enrolled an hour ago
- **WHEN** the user POSTs a new 20-second WAV to `/api/voice_enrollment`
- **THEN** the previous `embedding` SHALL be replaced (different bytes), the WAV file at `VOICE_ENROLLMENT_DIR/u_a.wav` SHALL be replaced (different size or content), `created_at` SHALL be later than the prior value, AND there SHALL still be exactly one row for `u_a`

#### Scenario: Sample longer than 30 seconds is rejected and WAV not retained

- **GIVEN** an authenticated user and a 45-second WAV
- **WHEN** the user POSTs to `/api/voice_enrollment`
- **THEN** the response SHALL be HTTP 422 with `error_code = "voice_enrollment.too_long"`, no `voice_enrollment` row SHALL be written, and the staged WAV SHALL be removed from disk

#### Scenario: Multi-speaker sample is rejected and WAV not retained

- **GIVEN** an authenticated user and a 20-second WAV containing two distinct speakers
- **WHEN** the user POSTs to `/api/voice_enrollment`
- **THEN** the response SHALL be HTTP 422 with `error_code = "voice_enrollment.invalid_sample"`, no `voice_enrollment` row SHALL be written, and the staged WAV SHALL be removed from disk


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/config.py
  - .env.example
tests:
  - packages/backend/tests/voice_enrollment/test_router.py
-->


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: apply_speaker_attribution renames the matched single-channel cluster to me when an enrollment exists

The backend SHALL extend `apply_speaker_attribution(meeting_id, repo, single_channel_provider=None, voice_enrollment_repo=None, current_user_id=None)` so that, when the selected strategy is `SingleChannelStrategy` AND `voice_enrollment_repo` is supplied AND a row exists for `current_user_id`, the helper SHALL:

1. Retrieve `cluster_embeddings: dict[int, np.ndarray]` from `SingleChannelStrategy.last_diarize_output.speaker_embeddings` joined to the strategy's internal cluster-id mapping.
2. Pass `(enrolled_embedding, cluster_embeddings, threshold)` to `VoiceEnrollmentMatcher.find_me_cluster(...)`.
3. If the matcher returns a cluster id `N`, rewrite every chunk in the post-strategy result whose `speaker == "speaker_cluster_N"` to `"me"`.

The DualChannelStrategy path SHALL skip the rename entirely (binary attribution is already correct from the ASR pipeline). The SingleChannelStrategy path SHALL skip the rename when (a) no enrollment exists, (b) the matcher returns `None`, or (c) `current_user_id` is `None`. When the rename runs successfully, the returned `AttributionResult.chunks_updated` SHALL include the renamed chunks.

#### Scenario: User has enrollment, single-channel meeting renames the matched cluster

- **GIVEN** user `u_a` has a `voice_enrollment` row, a finalized single-channel meeting with three speaker clusters where cluster 2's embedding matches the enrolled embedding above threshold, and three chunks each labelled `speaker_cluster_1 / 2 / 3` respectively
- **WHEN** `apply_speaker_attribution(meeting_id, repo, current_user_id="u_a", voice_enrollment_repo=ve_repo)` runs
- **THEN** the resulting chunks in DB SHALL have `speaker` values `speaker_cluster_1 / me / speaker_cluster_3`, AND `AttributionResult.chunks_updated` SHALL count the cluster-2 chunk as updated

#### Scenario: User has no enrollment, single-channel meeting keeps cluster labels untouched

- **GIVEN** user `u_b` has NO `voice_enrollment` row, and a finalized single-channel meeting with two clusters labelled `speaker_cluster_1` and `speaker_cluster_2`
- **WHEN** `apply_speaker_attribution(meeting_id, repo, current_user_id="u_b", voice_enrollment_repo=ve_repo)` runs
- **THEN** the chunks in DB SHALL retain their `speaker_cluster_1 / speaker_cluster_2` labels with no rename, AND the helper SHALL NOT raise

#### Scenario: Enrollment exists but no cluster passes threshold

- **GIVEN** user `u_a` has an enrollment, and a finalized single-channel meeting where no cluster's similarity reaches the threshold
- **WHEN** `apply_speaker_attribution(...)` runs
- **THEN** no chunk SHALL be renamed; all chunks keep `speaker_cluster_*` labels

#### Scenario: Dual-channel session ignores enrollment

- **GIVEN** user `u_a` has an enrollment, and a dual-channel meeting whose chunks are already labelled `me` / `counterparty`
- **WHEN** `apply_speaker_attribution(...)` runs
- **THEN** `chunks_updated == 0` AND `me` / `counterparty` labels remain unchanged


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/router.py
tests:
  - packages/backend/tests/speaker/test_finalize.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
-->


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: /settings/voice route lets the user record, preview, and save a 30-second voice sample

The frontend SHALL ship a standalone route `/settings/voice` that uses the browser `MediaRecorder` API to capture the user's microphone, with a hard cap of 30 seconds (recording auto-stops if the user does not stop manually). The page SHALL display a live RMS-based level meter while recording, an `<audio>` preview element after recording stops, "重新錄製 / Re-record" and "儲存 / Save" buttons, and the saved-state confirmation after a successful upload. All visible strings SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json` (per the locale-mirror invariant). The save action SHALL POST the recorded blob as `audio/wav` to `/api/voice_enrollment` and surface server-side validation errors via the localized error catalog.

#### Scenario: Recording auto-stops at 30 seconds

- **GIVEN** the user clicks "開始錄製" on `/settings/voice` and does not press stop
- **WHEN** 30 seconds elapse
- **THEN** the `MediaRecorder` SHALL stop automatically, the level meter SHALL hide, the preview `<audio>` element SHALL be populated with the recording blob, and the "儲存" button SHALL become enabled

#### Scenario: Save POSTs the recording and shows success confirmation

- **GIVEN** the user has recorded a 20-second sample and the preview is shown
- **WHEN** the user clicks "儲存"
- **THEN** the page SHALL POST to `/api/voice_enrollment` with the WAV payload, await the response, and on HTTP 200 SHALL display the localized confirmation text and disable further uploads until the user clicks "重新錄製"

#### Scenario: Server-side validation error surfaces localized message

- **GIVEN** the user recorded a sample but the backend rejected it with `error_code = "voice_enrollment.invalid_sample"`
- **WHEN** the failure response is received
- **THEN** the page SHALL render the localized error message resolved via the project's `localizedErrorMessage` helper, AND the "儲存" button SHALL remain enabled so the user can retry without re-recording


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-14
code:
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
tests:
  - packages/web/src/routes/settings/voice.test.tsx
-->

<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->