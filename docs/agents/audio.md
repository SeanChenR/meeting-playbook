# Audio capture — agent notes

> Slice 6 (`slice-06-mic-transcript-session`) outcome.
> Module: `packages/backend/meeting_playbook/audio/capture.py`.

## macOS microphone permission

The first time a user clicks "開始會議 / Start Meeting" after a fresh
terminal restart, macOS prompts for microphone access. The prompt is
attached to the terminal process (or whichever process actually opens
the audio stream). Two paths from there:

- **User clicks Allow** — `sounddevice.RawInputStream` opens, audio frames
  start arriving in the queue, the WS session proceeds normally.
- **User clicks Deny** — the stream constructor raises `PortAudioError`,
  which `AudioCaptureService` wraps as `CaptureDeviceUnavailable`. The
  router currently emits a generic `error` frame; future work could map
  it to `error_code: session.no_audio_device` for a localized
  「請打開麥克風權限」 prompt with deep-link instructions.

To regrant after deny: **System Settings → Privacy & Security → Microphone**
and toggle the terminal / Python process on. After regranting, restart
the dev server (`bun run dev`) — the permission cache is per-process.

## RECORDINGS_DIR — where WAV files live

WAV files are written under `~/MeetingPlaybook/recordings/{meeting_id}/me.wav`
by default. The base directory comes from the `RECORDINGS_DIR` env var
and the `~` is expanded at runtime.

This is intentionally outside the project tree:
- Survives `git clean -fdx` and worktree switches
- Recordings are user data (often private), not source / build artifacts
- Multi-checkout safe — each branch sees the same recordings instead of
  duplicating them

`.gitignore` defensively also blocks `*.wav` outside `tests/**` so a
mis-set `RECORDINGS_DIR=./recordings` cannot accidentally leak audio
into the repo.

## Sample rate and format

Capture is hardcoded 16 kHz mono int16 PCM — the right shape for
faster-whisper's input expectations. WAV files are written with the same
parameters via the stdlib `wave` module. Future ASR providers that need
a different rate would require a downstream resample step (out of scope
here).

## Silence detection

The capture service computes RMS over each incoming frame; sustained
silence (RMS below the configured threshold) for `silence_warning_after`
seconds emits exactly one `SilenceWarning` event. Subsequent
`SilenceWarning`s are suppressed until audio resumes (RMS rises above
threshold), so the client is not spammed.

The default threshold (`50.0` int16 RMS, ~ -56 dBFS) is well below
normal speech but above typical background noise on a quiet macOS desk.
Tune via `_SILENCE_RMS_THRESHOLD` if needed.
