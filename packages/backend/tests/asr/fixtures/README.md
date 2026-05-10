# ASR test fixtures

Short voice samples used by `tests/asr/test_whisper_provider.py` and
the dual-stream session integration tests in slice-07.

All WAVs are **mono, 16 kHz, int16 PCM** — the format `WhisperProvider`
expects from `AudioCaptureService`.

## Fixtures

| File | Duration | Voice / Source | Purpose |
| ---- | -------- | -------------- | ------- |
| `short_speech_zh.wav` | ~3s | macOS `say -v Mei-Jia` (zh-TW) | Slice 6: validates Chinese transcription end-to-end |
| `short_speech_en.wav` | ~3s | macOS `say -v Samantha` (en-US) | Slice 6: validates English transcription |
| `counterparty_short.wav` | ~6s | macOS `say -v Daniel` (en-GB, male) | Slice 7: dual-stream test counterparty audio (different voice from `short_speech_en.wav` so the two streams produce distinguishable transcripts) |

## Regenerating

To rebuild a fixture (e.g. after changing wording):

```sh
# Pick any voice via `say -v ?`
say -v Daniel -o /tmp/out.aiff "Hello Sean, thanks for setting up this meeting. I'd like to discuss the Q3 numbers when you're ready."
ffmpeg -y -i /tmp/out.aiff -ar 16000 -ac 1 -sample_fmt s16 counterparty_short.wav
```

`-ar 16000 -ac 1 -sample_fmt s16` is non-negotiable — anything else breaks
the `WhisperProvider` ingest path (which assumes mono int16 PCM).
