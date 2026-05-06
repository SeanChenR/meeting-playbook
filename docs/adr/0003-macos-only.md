# ADR-0003: macOS-only target (Apple Silicon)

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The user runs macOS Tahoe (26.4.1) on a MacBook Pro 14-inch M3 Pro 18GB. The audio capture choice (ADR-0004 — BlackHole) is macOS-only. The local ASR options (ADR-0005) all benefit from Apple Silicon Metal acceleration.

## Decision
Target macOS only for the MVP. Apple Silicon is assumed.

## Consequences
- BlackHole, ScreenCaptureKit (future), and other mac-native APIs are options.
- Cross-platform code is not required; do not pay for cross-platform abstractions.
- Hardware specs (M3 Pro 18GB) are the planning baseline for memory / performance budgets, including ASR model size.

## Alternatives considered
- **Cross-platform from day one** — the audio capture story differs per OS (BlackHole, WASAPI loopback, PulseAudio loopback). Premature complexity.
- **Linux-first** — the user works on macOS daily; Linux would not get used.
