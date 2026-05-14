# Diarization latency comparison

Appended by `tests/speaker/test_pyannote_real_audio.py`. ADR-0029 cites the most recent entry for the v1.1 baseline.

## 2026-05-14T18:01:07+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 37.45s
- p95 latency: 43.17s
- p95 realtime ratio: 0.51x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-14T18:20:51+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 39.29s
- p95 latency: 45.10s
- p95 realtime ratio: 0.53x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]
