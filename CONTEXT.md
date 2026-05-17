# Meeting Playbook — Project Context

## Why this exists
The user (Sean) does not want to choose between "take notes" and "be present in the conversation". Existing SaaS tools cost $10-30/month and store recordings on third-party clouds. This is a personal tool, local-first, with auth from day one so it can be deployed later if useful.

## What it does
Three lifecycle phases of one meeting:

1. **Pre-meeting (會前)** — auto-generates a playbook draft from Google Calendar event metadata (title, attendees, description, time). The user refines the structured playbook fields (objective, counterparty profile, anticipated topics, anticipated objections, talking points, red lines).

2. **In-meeting (會中)** — captures audio from both sides simultaneously via BlackHole (counterparty's voice) and microphone (the user's voice). Runs ASR every ~10 seconds, shows transcript live in the middle column. The user can press "Get Advice" for a single-shot tactical suggestion, or chat with an AI advisor that has access to the recent transcript + the full playbook.

3. **Post-meeting (會後)** — produces a markdown summary with decisions made, action items, key discussion points. Exportable to file.

## Domain language (use these terms exactly in code & documentation)

| Term | Meaning |
|------|---------|
| **Playbook** | Structured prep document for one meeting |
| **Playbook field** | One of: objective, counterparty profile, anticipated topics, anticipated objections, talking points, red lines |
| **Counterparty (對方)** | The other side of the conversation; speaker tag for the BlackHole-sourced audio stream |
| **Me (我方)** | The user; speaker tag for the microphone-sourced audio stream |
| **Pre-meeting / In-meeting / Post-meeting (會前 / 會中 / 會後)** | The three lifecycle phases of a single meeting |
| **Tactical advisor** | One-click LLM call returning realtime advice based on the last 60s of transcript + the full playbook |
| **ASR Provider** | Pluggable transcription engine implementing the `ASRProvider` interface (current providers: Whisper, VibeVoice-ASR) |
| **Dual-channel capture** | BlackHole + microphone produce two synchronized audio streams; speaker identity is tagged at the source, no diarization is required |
| **Live capture (即時擷取)** | The real-time path that records audio with `sounddevice` during an active session — either `Dual-channel capture` (mic + BlackHole) or `Single-channel mode` (mic only). Always produces `recording.source = 'live'` rows |
| **Offline ingest (離線匯入)** | The post-hoc path where the user uploads a pre-recorded audio file (wav / mp3 / m4a / aac / flac / ogg) via the tus protocol; backend transcodes to 16kHz mono WAV and runs ASR through the `Single-channel mode` finalize path. Produces `recording.source = 'offline'` rows |
| **Single-channel mode (面對面模式)** | Capture path used when only a single microphone Recording exists (e.g. face-to-face meeting); a `DiarizationProvider` partitions the audio into speaker clusters because there is no per-stream source tag to rely on |
| **Speaker cluster (與會者一 / 與會者二 / ...)** | Unsupervised speaker grouping output from `DiarizationProvider` under `Single-channel mode`; stored on `transcript_chunk.speaker` as `speaker_cluster_{N}` (1-based) and rendered in the UI as 「與會者 N」 |
| **Voice enrollment sample (聲紋樣本)** | A one-time 30-second WAV the user records via `/settings/voice`; its pyannote-derived embedding lets `Single-channel mode` automatically rename the matching speaker cluster to `me` at session finalize (per ADR-0029 + slice 13) |
| **Recording window** | The 30-day retention window for raw WAV audio files; older recordings are auto-deleted but transcripts are preserved |
| **Meeting** | A single timeboxed event with one playbook, one set of audio recordings, one transcript, and (post-completion) one summary |
| **Mini-player** | Sticky-bottom audio control bar on the meeting detail page that plays a transcript chunk's underlying audio slice; six playback speeds, persists to `localStorage.miniPlayerRate` (slice-16) |
| **Transcript chunk edit** | User-initiated correction of an ASR chunk's text via `PATCH /api/meetings/{id}/transcript_chunks/{cid}`; speaker / timestamps / asr_provider_used remain immutable. `text_edited_at` stamps each successful edit (slice-16) |
| **Transcript color scheme** | One of five hard-coded palettes (default / vivid / pastel / high-contrast / grayscale) the user can apply to `speaker_cluster_<N>` rendering; per-cluster overrides land in `localStorage`. `me` and `counterparty` keep their semantic colours and are not customisable (slice-16) |
| **Tag (標籤)** | Per-user 自訂的扁平分類標籤；可掛到 meeting 上做 list / kanban / calendar 過濾。Per-user case-insensitive 唯一；單一 meeting 最多 10 個；色票從 preset palette 挑（per slice-17）|
| **Meeting attachment (會議附件)** | User-uploaded image / PDF / docx / txt / md attached to a meeting via `/api/meetings/{id}/attachments`. Per-meeting quota: 5 files / 30 MB. Sweeps under the same 30-day `Recording window` retention as raw audio; row + on-disk file removed together (slice-20a) |

## Boundaries
- **Single user.** No team / sharing / multi-tenant.
- **macOS only.** Apple Silicon target (developed on M3 Pro 18GB).
- **Cloud LLM, local ASR by default.** Vertex AI handles language understanding. ASR runs locally for free unless the user picks a cloud provider.
- **Auth from day one.** Better Auth + Google OAuth + TOTP 2FA. Not strictly required for localhost use, but bakes future-deploy-readiness in early.

## Non-goals (v1)
- Mobile / Windows / Linux clients
- Multi-speaker diarization 限制於 Single-channel mode；Dual-channel capture 仍為 binary（per ADR-0016 + ADR-0029）
- Realtime streaming summary (post-meeting summary is batch-only)
- Calendar providers other than Google Calendar
- Gmail / Notion / Linear / Slack integration
- Cloud sync / multi-device sync
- Speaker identification across different meetings

## Stakeholders
- **User**: Sean — sole user and owner.
- **AI assistants**: Claude Code, Codex, etc. — editing this codebase under explicit instruction.

## External dependencies the user must set up once
1. PostgreSQL via Homebrew (already installed)
2. BlackHole 2ch (`brew install blackhole-2ch`) and a Multi-Output Device in macOS Audio MIDI Setup
3. A GCP project with Vertex AI API + Google Calendar API enabled (the same project will host the OAuth client used by Better Auth)
4. A Google OAuth Web Client whose redirect URI is `http://localhost:3001/api/auth/callback/google`
5. A TOTP authenticator (Authy / 1Password / Google Authenticator) for 2FA enrollment

## Three-process model (dev)
- **Vite** (5173) — frontend dev server with HMR, proxies `/api/*` to `:3001`
- **Bun.serve + Better Auth** (3001) — handles `/api/auth/*` natively, proxies all other `/api/*` to `:8000`
- **FastAPI** (8000) — audio capture, ASR, LLM, business endpoints

`bun run dev` starts all three via `concurrently`.
