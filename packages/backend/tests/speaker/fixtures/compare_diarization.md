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

## 2026-05-14T20:09:45+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 35.51s
- p95 latency: 35.92s
- p95 realtime ratio: 0.43x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-14T20:18:51+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 37.20s
- p95 latency: 37.53s
- p95 realtime ratio: 0.44x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-15T08:48:02+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 42.00s
- p95 latency: 53.92s
- p95 realtime ratio: 0.64x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-15T08:52:34+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 39.74s
- p95 latency: 44.22s
- p95 realtime ratio: 0.52x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-15T08:59:01+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 38.89s
- p95 latency: 50.73s
- p95 realtime ratio: 0.60x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]

## 2026-05-15T09:04:35+00:00 — multi_speakers_zh.wav (84.4s)

- runs: 3
- p50 latency: 41.53s
- p95 latency: 59.23s
- p95 realtime ratio: 0.70x (diarize_seconds / audio_seconds; < 1.0 = faster than realtime)
- cluster counts per run: [2, 2, 2]
