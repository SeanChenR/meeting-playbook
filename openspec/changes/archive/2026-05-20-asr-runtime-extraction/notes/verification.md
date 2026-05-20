# asr-runtime-extraction — verification notes

## Status

Pending — Sean's hands-on session on M3 Pro 18 GB. The runtime needs the
real Qwen3-ASR-1.7B weights (~5 GB) and a working BlackHole + microphone
device pair to exercise the acceptance criteria end-to-end.

## Acceptance criteria checklist (per design Implementation Contract)

- [ ] (a) `bun run dev` launches four prefixed log lines —
  `[web]`, `[auth]`, `[backend]`, `[asr]` — and the asr-runtime emits
  `asr-runtime listening on http://127.0.0.1:8100`.
- [ ] (b) First "開始會議" press (dual mode): AsrLoadingDialog appears
  and disappears within 5 seconds after warmup. Re-pressing right after
  triggers no loading flicker (model stays warm).
- [ ] (c) After ~10 s of speech the first `transcript_chunk` arrives in
  the workspace transcript pane.
- [ ] (d) `kill -9` the asr-runtime process, then press 開始會議: the
  frontend surfaces an `asr.runtime_unavailable` toast / alert; the
  meeting status rolls back to `completed` (not stuck in `in_progress`).
- [ ] (e) Backend reload (`touch packages/backend/meeting_playbook/server.py`):
  the asr-runtime stays running and the next 開始會議 dialog closes in
  < 1 second.
- [ ] (f) Settings → preferences shows ONE ASR card (Qwen3-ASR) — no
  Whisper logo, no Whisper label, no broken image.

## Manual verification log

(populate during the live session)

| Criterion | Result | Evidence (screenshot / log path) |
| --------- | ------ | -------------------------------- |
| (a)       |        |                                  |
| (b)       |        |                                  |
| (c)       |        |                                  |
| (d)       |        |                                  |
| (e)       |        |                                  |
| (f)       |        |                                  |

## Test suite results

- [ ] Web: `bun --filter @meeting-playbook/web test` — green (already
  confirmed during apply: 722 pass / 17 skip / 0 fail).
- [ ] Backend: `cd packages/backend && uv run pytest` — pending.
- [ ] ASR runtime: `cd packages/asr-runtime && uv sync && uv run pytest`
  — pending (requires first-time uv sync; downloads torch + qwen-asr).

## Outstanding follow-ups (out of scope for this change)

- No automatic restart on runtime crash. Tracked as a `Risks / Trade-offs`
  entry in `design.md` and called out in ADR-0030. Future improvement:
  systemd / launchd unit or `concurrently --kill-others` so a runtime
  crash explicitly takes the whole dev stack down.
- `RemoteAsrRuntimeClient` does NOT use the WebSocket route yet — every
  chunk goes through the HTTP `/v1/transcribe/chunk` endpoint. The WS
  route is implemented and tested in the runtime but not wired into the
  backend session loop. Acceptable trade-off for the first cut; switch
  the backend to the WS path once latency profiling shows it matters.
