# ADR-0004: BlackHole 2ch for dual-channel audio capture

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
To produce a meaningful transcript with speaker tags, the system needs the counterparty's voice and the user's voice as separate streams. Four options were evaluated:

| Option | Captures all meeting apps | Works with headphones | Onboarding cost |
|--------|---|---|---|
| BlackHole + Multi-Output Device | Yes | Yes | High (one-time) |
| macOS ScreenCaptureKit | Yes | Yes | Medium (Swift helper) |
| Browser `getDisplayMedia` | No (browser tabs only) | Yes | Low |
| Microphone-only environmental capture | Yes | **No** (headphones break it) | None |

## Decision
Use BlackHole 2ch. The user creates a Multi-Output Device in macOS Audio MIDI Setup that routes meeting app output to both the speakers/headphones and to BlackHole. The backend reads two streams: BlackHole (counterparty) and the system microphone (user).

## Consequences
- One-time setup pain for the user, documented in `docs/BLACKHOLE_SETUP.md` (to be written in implementation phase).
- Works with all meeting apps including Zoom desktop, Teams, FaceTime, native VOIP.
- Future deploy to other users would require the same BlackHole onboarding; ScreenCaptureKit is the future migration path (post-MVP).
- The two streams are inherently separated by source — no diarization model needed (ADR-0016).

## Alternatives considered
- **Microphone-only** — fails when the user wears headphones (most real meetings).
- **ScreenCaptureKit** — cleaner UX but requires a Swift helper binary, splits the stack across three languages.
- **Browser `getDisplayMedia`** — only captures browser-tab audio; useless for Zoom desktop.
