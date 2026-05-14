> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/24
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
> Depends on: slice-12-speaker-hybrid (parked, build complete)

## Why

S12 把面對面會議的 single-channel 路徑做出來了，但分出的 cluster 只能標 `speaker_cluster_1 / 2 / 3...`，使用者每次會議結束都要手動辨識「哪個 cluster 是我」。S13 讓使用者預錄一次自己的 30 秒聲紋樣本（Voice enrollment sample），之後所有 single-channel 會議自動把符合的 cluster 改標為 `me`，省掉每次手動命名的步驟。

## What Changes

- 新增 schema `voice_enrollment(user_id PK, sample_wav_path, embedding bytea, created_at)`，per-user 一筆，重新上傳會覆蓋既有 row
- 新 `VoiceEnrollmentRepository`：管理 WAV 檔 + embedding bytes 的存取
- 新 `VoiceEnrollmentMatcher`：拿 single-channel `DiarizeOutput.speaker_embeddings` + 已 enroll 的 embedding，回傳 `{cluster_id: True}` 表示哪一個 cluster 是 me
- 新 endpoint `POST /api/voice_enrollment`：接 16kHz mono WAV (≤30s, ≤5MB)，呼叫 pyannote pipeline 抽 embedding，存檔 + 寫 row；驗證樣本能產出非零 embedding（純靜音 reject）
- 新前端路由 `/settings/voice`（獨立路由，S19 settings shell 上線後可重用此頁面）：30 秒 mic 錄音 + 即時音量計 + 預聽 / 重錄 / 儲存
- 既有 `apply_speaker_attribution`（S12 落地）擴：single-channel finalize 結束後若該 user 有 enrollment row → 呼叫 `VoiceEnrollmentMatcher` → 把符合的 cluster 從 `speaker_cluster_<N>` rename 成 `me`
- 新環境變數 `VOICE_ENROLLMENT_DIR`（聲紋樣本 WAV 本機儲存目錄）寫入 `.env.example`
- `CONTEXT.md` glossary 加「Voice enrollment sample (聲紋樣本)」

## Non-Goals

- 多人 enrollment（例如「主管」、「常見對手」聲紋）— v1.1 只 enroll 「me」一個聲音；多 speaker enrollment 排未來 ADR
- Counterparty 自動命名（counterparty 在 dual-channel 已從 stream source 標好；single-channel 場景多人通常是與會者，沒有「永遠的對手」聲紋意義）
- 跨會議 speaker 識別（per CONTEXT.md non-goal「Speaker identification across different meetings」維持不動，本 slice 只在「session finalize」的 single 步驟內做匹配）
- Enrollment refinement feedback loop（使用者手動 rename N 次後建議重新 enroll，列 v1.2 backlog #4 brainstorm）
- Voice biometric 身份驗證 / 登入（聲紋只用於 attribution，不做 auth）
- 修改 `SingleChannelStrategy` 內部 — rename 走 `apply_speaker_attribution` 後處理步驟，保留 strategy 純粹做 diarization

## Capabilities

### New Capabilities

- `voice-enrollment`: 使用者 30s 聲紋樣本的儲存、embedding 抽取、API、UI、與 session finalize 整合（auto-rename me）。

### Modified Capabilities

- `meeting-session`: `transcript_chunk.speaker` 在 single-channel 模式新增 `"me"` 為有效值（前提：該使用者已 enroll 且某 cluster 匹配成功）；既有 dual-channel 行為與 single-channel 無 enrollment 行為皆不變。

## Impact

- Affected specs:
  - New: `openspec/specs/voice-enrollment/spec.md`
  - Modified: `openspec/specs/meeting-session/spec.md`
- Affected code:
  - New: `packages/backend/meeting_playbook/voice_enrollment/__init__.py`, `packages/backend/meeting_playbook/voice_enrollment/models.py`, `packages/backend/meeting_playbook/voice_enrollment/repository.py`, `packages/backend/meeting_playbook/voice_enrollment/matcher.py`, `packages/backend/meeting_playbook/voice_enrollment/embedding.py`, `packages/backend/meeting_playbook/voice_enrollment/router.py`, `packages/backend/alembic/versions/XXXX_voice_enrollment.py`, `packages/web/src/routes/settings/voice.tsx`, `packages/web/src/routes/settings/voice.test.tsx`, `packages/web/src/lib/voice-enrollment-api.ts`
  - Modified: `packages/backend/meeting_playbook/speaker/finalize.py`, `packages/backend/meeting_playbook/server.py`, `packages/backend/meeting_playbook/config.py`, `packages/web/src/locales/zh-TW.json`, `packages/web/src/locales/en.json`, `packages/web/src/route-tree.tsx`, `CONTEXT.md`, `.env.example`
  - Removed: (none)
