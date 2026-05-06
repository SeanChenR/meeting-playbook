# ADR-0020: 30-day recording retention with auto-cleanup

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Each one-hour meeting produces ~110MB of dual-channel WAV. Storing all recordings forever costs ~22GB/year for a busy schedule. Storing none prevents post-hoc ASR engine comparison (which the user explicitly wants — ADR-0005).

## Decision
- Raw WAV files live under `~/MeetingPlaybook/recordings/` for **30 days** by default.
- A daily background job deletes recordings older than 30 days.
- Transcripts, playbooks, summaries, and chatbox history are kept indefinitely (text is cheap).
- The retention window is configurable via env var (`RECORDING_RETENTION_DAYS`).

## Consequences
- Disk footprint stays bounded.
- The 30-day window covers the user's A/B test of Whisper vs VibeVoice-ASR on real meetings.
- Once deleted, "rerun ASR with a new engine on this meeting" stops working for that meeting.

## Alternatives considered
- **Keep everything** — unbounded disk cost.
- **Keep nothing** — kills the ASR comparison use case.
- **Keep N most recent** — count-based eviction is less predictable than time-based for the user.
