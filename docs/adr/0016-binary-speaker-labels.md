# ADR-0016: Binary speaker labels with per-meeting custom display names

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
B2B meetings are often N-on-N (e.g., 2 vs 3). True multi-speaker diarization is a separate ML problem (pyannote.audio etc.) with mixed quality. The dual-channel capture (ADR-0004) already gives speaker identity at the source: BlackHole = counterparty, microphone = me.

## Decision
- Speaker tagging is binary at the data layer: `counterparty` and `me`.
- Each meeting has two free-text display name fields (e.g., "林經理" and "Sean") that the user sets when starting the meeting.
- The UI renders the display names; the schema stores the binary labels.
- Multi-person diarization within a side (e.g., distinguishing two counterparty voices) is out of v1 scope.

## Consequences
- Schema is simple: a `transcript_chunk` row has a `speaker` enum (`counterparty | me`), and the meeting carries two display strings.
- No diarization model to maintain.
- If two counterparty voices on the BlackHole stream become a real pain, a future ADR can add an optional pyannote pass.

## Alternatives considered
- **Always "對方 / 我"** — slightly less personal; per-meeting display names cost almost nothing.
- **pyannote diarization on each stream** — quality is meeting-dependent, training/tuning overhead, and the failure mode (mislabeling) is worse than no labeling.
