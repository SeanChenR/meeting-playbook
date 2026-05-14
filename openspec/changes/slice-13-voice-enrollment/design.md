## Context

S12 把面對面會議 single-channel pipeline 接通了，但分出來的 cluster 只有匿名標籤（`speaker_cluster_1 / 2 / 3...`）。對使用者來說，每次會議結束都要看 transcript 重新辨識「哪一個 cluster 是我」。S13 解這個 UX 缺口：讓使用者**預錄一次**自己的 30 秒聲音樣本，之後每場 single-channel 會議結束時自動把對應 cluster 改標為 `me`，其他 cluster 維持 `speaker_cluster_*`。

「對方」不做 enrollment，理由：對方在 dual-channel 已從 stream source 標好；single-channel 多人會議裡「對方」可能是任何人，沒有「永遠的對手聲紋」的意義。

技術上重用 pyannote.audio 既有 pipeline 的 `DiarizeOutput.speaker_embeddings` 輸出，不額外裝 embedding model；matching 純走 cosine similarity 走 numpy。

## Goals / Non-Goals

**Goals**

- 使用者預錄一次 30 秒 WAV 樣本後，single-channel 會議結束時匹配 cluster 自動 rename 為 `me`。
- 不影響既有 dual-channel 行為（slice-12 已建立的 regression baseline 仍 0 影響）。
- Voice enrollment 完全可選 — 沒 enrollment 也不阻擋 single-channel 流程（cluster 仍標 `speaker_cluster_*`）。
- 走 standalone `/settings/voice` 路由，S19 settings shell 上線時可直接搬進 sub-nav。

**Non-Goals**

- 多人 enrollment（counterparty / 同事 / 客戶聲紋）— 留未來 ADR。
- 跨會議 speaker identity（不在 voice_enrollment 上掛 meeting-history embedding clustering）。
- 聲紋當登入認證使用（biometric auth）。
- 修改 `SingleChannelStrategy` 內部 — rename 放 `apply_speaker_attribution` 層做後處理，strategy 純粹做 diarization。
- 增量 enrollment / refinement loop（使用者改 N 次自動建議重新 enroll）。

## Decisions

### Embedding 來源：重用 pyannote DiarizeOutput.speaker_embeddings

不裝獨立 embedding model，重用 S12 已導入的 pyannote.audio `pyannote/speaker-diarization-3.1` pipeline。enrollment 時把 30 秒 WAV 餵進 pipeline，取 `DiarizeOutput.speaker_embeddings`（shape `(n_speakers, embedding_dim)`），驗證 `n_speakers == 1`，把唯一那條 embedding 當「me 的聲紋」存 DB。**Alternative considered**：另裝 `pyannote/embedding` 或 `wespeaker-voxceleb-resnet34-LM`——被否決，會增加 ~300MB 第二個模型下載且 embedding 空間跟 diarization pipeline 不通用，匹配時還要互相 align。

### Matching：cosine similarity + tunable threshold

Single-channel finalize 時，從該會議的 `DiarizeOutput.speaker_embeddings` 拿每個 cluster 的 embedding，對 enrolled embedding 算 cosine similarity，**取最高分**作為候選 cluster。若最高分 ≥ `VOICE_ENROLLMENT_MATCH_THRESHOLD`（default 0.5），rename 該 cluster；其他 cluster 不動。若最高分 < threshold → 全 cluster 維持原 `speaker_cluster_*`。**Alternative considered**：所有 ≥ threshold 的 cluster 都 rename 成 me——被否決，me 在一場會議只可能是一個聲音，多個高相似度通常代表 threshold 設太低或環境噪音造成 cluster 細分，rename 多個會讓使用者更困惑。

### Integration point：apply_speaker_attribution 後處理

不動 `SingleChannelStrategy`。在既有 `apply_speaker_attribution`（slice-12 落地的 finalize helper）裡，single-channel 路徑跑完 `strategy.assign_speakers(...)` 之後加入「voice enrollment rename」步驟：查使用者 enrollment row，若存在 → 抓該會議 pipeline 已產出的 embeddings → 算 similarity → 找匹配 cluster → 改寫 `result chunks` 內所有 `speaker == "speaker_cluster_<matched>"` 為 `"me"`。**Alternative considered**：在 `SingleChannelStrategy.assign_speakers` 內呼叫 matcher——被否決，strategy 跟 voice enrollment 耦合，未來 strategy 想換 impl（cloud diarization）會把 matching 邏輯也綁進去。**Alternative considered**：另寫 wrapper strategy `EnrollmentAwareSingleChannel(SingleChannelStrategy)`——被否決，多一層繼承讓 `select_strategy` 邏輯複雜化，目前直接放 finalize 後處理最簡。

### Embedding 暴露問題：把 DiarizeOutput.speaker_embeddings 傳出 SingleChannelStrategy

`SingleChannelStrategy.assign_speakers` 目前只回 list[TranscriptChunk]，丟掉 pipeline 中間產物。需要新增第二個輸出 channel 把 embeddings 傳出來給 finalize 後處理用。實作上加 `SingleChannelStrategy.last_diarize_output: DiarizeOutput | None` 屬性（per-instance），每次 `diarize` 完更新；finalize helper 讀這個屬性。**Alternative considered**：讓 `assign_speakers` 改回 tuple `(chunks, embeddings)`——被否決，影響 protocol 簽名 + dual-channel 沒有 embeddings 拿什麼回；instance attribute pattern 雖然有點 stateful 但隔離在 single-channel impl 內，dual-channel 不受影響。**Alternative considered**：finalize 自己再跑一次 pyannote 抽 embedding——被否決，30 分鐘會議跑兩次 diarization 太貴。

### 30 秒上限與檔案驗證

POST `/api/voice_enrollment` 接 `audio/wav` (16kHz mono, ≤30s, ≤5MB)。Server 在抽 embedding 前驗：(a) 檔案格式 / sample rate 對；(b) pyannote 跑完回的 `n_speakers == 1`；(c) `embedding` 非全零（純靜音樣本會被偵測）。任一驗證失敗 → HTTP 422 `voice_enrollment.invalid_sample` 配清楚錯誤訊息。**Alternative considered**：放長到 60 秒——被否決，pyannote 30s 對個人聲紋已足夠穩；長 sample 反而拉高 endpoint latency 沒有對應收益。

### `voice_enrollment.embedding` 儲存：bytea + numpy.tobytes

embedding 是 fixed-shape float32 vector（pyannote x-vector 通常 `(192,)` 或 `(256,)`）。存 `bytea`，用 `numpy.tobytes()` / `numpy.frombuffer(bytes, dtype=np.float32)` 互轉。Schema 不存 shape 元資訊——讀取時用 `(embedding_bytes_length // 4,)` 還原（float32=4 bytes）。Alternative considered: 存 JSON / PostgreSQL `vector(192)` (pgvector)——被否決，JSON 浪費空間（每個 float 變字串）；pgvector 拉一個非必要 extension 進來，slice-13 範圍不需要向量索引能力。

## Implementation Contract

- **新模組 `packages/backend/meeting_playbook/voice_enrollment`** 暴露：
  - `VoiceEnrollment` SQLAlchemy model：`(user_id PK, sample_wav_path, embedding, created_at)`。
  - `VoiceEnrollmentRepository.get_for_user(user_id) -> VoiceEnrollment | None`、`upsert(user_id, wav_path, embedding) -> VoiceEnrollment`。
  - `compute_enrollment_embedding(wav_path) -> bytes`：跑 pyannote pipeline，驗 1 speaker，回 float32 embedding bytes；違反條件 raise `InvalidEnrollmentSample`。
  - `VoiceEnrollmentMatcher.find_me_cluster(enrolled_embedding: bytes, cluster_embeddings: dict[int, np.ndarray], threshold: float) -> int | None`：算 cosine similarity，回最高分且 ≥ threshold 的 cluster_id，否則回 None。
  - `voice_enrollment_router`（FastAPI APIRouter）：`POST /api/voice_enrollment` 接 multipart wav，呼叫 `compute_enrollment_embedding` + `upsert`，回 `{enrolled_at}`；驗證失敗回 HTTP 422。
- **既有 `packages/backend/meeting_playbook/speaker/finalize.py`** 擴：
  - 改 `apply_speaker_attribution` 簽名加可選 `voice_enrollment_repo`、`current_user_id`、`match_threshold`。
  - SingleChannelStrategy 路徑跑完 `strategy.assign_speakers(...)` 後，若 `voice_enrollment_repo.get_for_user(user_id)` 回非 None：抓 `strategy.last_diarize_output.speaker_embeddings` → `VoiceEnrollmentMatcher.find_me_cluster(...)` → 把 result chunks 內所有 `speaker == "speaker_cluster_<matched_id>"` 改寫為 `"me"`，回傳同樣的 `list[TranscriptChunk]`（保持 immutability rule）。
- **既有 `packages/backend/meeting_playbook/speaker/strategy.py`** 擴 `SingleChannelStrategy`：
  - 新 instance attribute `last_diarize_output: DiarizeOutput | None`（default `None`），每次 `assign_speakers` 結束前更新。
  - DualChannelStrategy 無此屬性。
- **既有 `packages/backend/meeting_playbook/sessions/router.py`** finalize 區段：呼叫 `apply_speaker_attribution` 時傳入 user_id 與 voice_enrollment_repo dependency。
- **新 Alembic migration** `XXXX_voice_enrollment.py`：建 table；down 是 drop。
- **新前端路由 `/settings/voice`**：
  - `MediaRecorder` API 抓 mic、limited 至 30s（hard cutoff）+ 即時音量計（顯示 RMS 0–100%）。
  - 預聽按鈕（`<audio>` element with `src=URL.createObjectURL(blob)`）+ 重錄 + 儲存。
  - 儲存 = `POST /api/voice_enrollment` multipart；成功顯示「聲紋已儲存」(zh-TW) / "Voice sample saved" (en)；失敗顯示 error_code 對應的 i18n 訊息。
- **`CONTEXT.md` glossary** 加「Voice enrollment sample (聲紋樣本)」一條。
- **`.env.example` + `config.py`** 新增 `VOICE_ENROLLMENT_DIR`（聲紋樣本 WAV 儲存目錄，default `~/MeetingPlaybook/voice_enrollments`）與 `VOICE_ENROLLMENT_MATCH_THRESHOLD`（default `0.5`）。

**Scope boundary** — In scope：voice_enrollment 模組、apply_speaker_attribution 後處理擴、SingleChannelStrategy 暴露 last_diarize_output、Alembic migration、`/settings/voice` 前端路由、config / env / CONTEXT.md / i18n。Out of scope：counterparty enrollment、跨會議 speaker identity、enrollment 自動 refinement、settings shell（slice-19）、聲紋 auth。

## Risks / Trade-offs

- **30 秒樣本不夠穩**（環境噪音 / 麥克風品質 / 使用者語速） → match threshold 拉高（0.5 → 0.6）+ POST 端驗證 embedding 不是全零；萬一還是 mis-match，使用者可手動刪除 enrollment 重來。
- **SingleChannelStrategy.last_diarize_output 是 stateful**，併發 `assign_speakers` 呼叫會 race → 一個會議 finalize 對一個 strategy instance；session router 已 per-meeting 建 strategy，不共用，目前路徑安全。在 `apply_speaker_attribution` 結束時 set `last_diarize_output = None` 釋放 reference，避免長時間占記憶體。
- **cluster_embeddings 對應問題**：pyannote DiarizeOutput.speaker_embeddings 索引順序對應到 annotation 內的 speaker label（`SPEAKER_00`、`SPEAKER_01`...）；我們的 cluster_id 是 `_annotation_to_segments` 自己 first-seen 重編號（1-based），需要保留 label→cluster_id 對照。在 PyannoteProvider 內把 mapping 一起回傳給 SingleChannelStrategy 用。
- **使用者 enroll 後刪除帳號**：voice_enrollment row 依 FK 到 user.id（Better Auth tables）— Alembic migration 加 `ON DELETE CASCADE`，使用者刪帳號時聲紋自動清掉。WAV 檔案 retention：跟 user 同壽命，無 30 天 expiry（聲紋不是 recording window 概念）。

## Migration Plan

- 新 Alembic migration `XXXX_voice_enrollment`：create table。Up 加 ON DELETE CASCADE FK。Down 是 drop。
- Rollout：合主 branch、跑 dual-channel 一週確認 regression-safe（finalize 路徑多了 conditional rename，無 enrollment 時 short-circuit）。
- Rollback：把 `apply_speaker_attribution` 內的 voice_enrollment 區段用 feature flag `VOICE_ENROLLMENT_ENABLED`（default true）包住，off 時跳過。緊急時環境變數 off 即可。

## Open Questions

- pyannote 4.x `DiarizeOutput.speaker_embeddings` 在 single-speaker 樣本上回傳的 shape / dtype 需要實測確認（apply 時跑一個 enrollment 流程驗證）。
- match threshold 0.5 是業界 x-vector default，但 pyannote-3.1 的 embedding space 可能不同；需要拿 Sean 自己 enrolled 之後比對「自己再講」vs「YouTube speaker」的 similarity 校準。校準路徑：apply 階段加 debug log 把 similarity 印出來，前 5 次會議後決定要不要調 threshold。
