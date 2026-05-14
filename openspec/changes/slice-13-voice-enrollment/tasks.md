## 1. Schema 與 config 落地

- [x] 1.1 [P] 新增 Alembic migration `alembic/versions/XXXX_voice_enrollment.py`：建立 `voice_enrollment` 表（columns 依 spec，特別注意 `embedding` 欄位用 `BYTEA` 對應設計決策「`voice_enrollment.embedding` 儲存：bytea + numpy.tobytes」），FK `user_id` → `user.id` ON DELETE CASCADE；up 後 `\d voice_enrollment` 在 psql 看得到該 schema，down 後該表消失；新測 `tests/test_alembic_voice_enrollment.py` 跑 upgrade → downgrade → upgrade 三輪驗證可逆，落實 `voice_enrollment table stores one embedding per user` requirement。
- [x] 1.2 [P] 在 `packages/backend/meeting_playbook/config.py` 加 `voice_enrollment_dir: str = "~/MeetingPlaybook/voice_enrollments"`、`voice_enrollment_match_threshold: float = 0.5`、`voice_enrollment_enabled: bool = True`；在 `.env.example` 加對應註解區段；驗證 `grep VOICE_ENROLLMENT_DIR .env.example` 命中。

## 2. Embedding 抽取 + Matcher（voice-enrollment 核心邏輯）

- [x] 2.1 [P] 在 `packages/backend/meeting_playbook/voice_enrollment/embedding.py` 實作 `compute_enrollment_embedding(wav_path) -> bytes`，**行為**：呼叫專案的 pyannote pipeline、讀 `DiarizeOutput.speaker_embeddings`、驗證 `n_speakers == 1` 且 embedding 非全零、回 `numpy.ndarray.tobytes()`；違反任一條件 raise `InvalidEnrollmentSample`。本 task 落實設計決策「Embedding 來源：重用 pyannote DiarizeOutput.speaker_embeddings」。Red tests 三條：multi-speaker fixture → reject；silent fixture → reject；single-speaker fixture → 回 bytes length % 4 == 0 且開頭非全零，落實 `compute_enrollment_embedding rejects samples that do not produce a single-speaker embedding` requirement。
- [x] 2.2 [P] 在 `packages/backend/meeting_playbook/voice_enrollment/matcher.py` 實作 `VoiceEnrollmentMatcher.find_me_cluster(enrolled_embedding, cluster_embeddings, threshold=0.5)`，**行為**：對每個 cluster 算 cosine similarity、取最高分且 ≥ threshold 者回傳 cluster_id；否則回 None；輸入皆不可被 mutate。本 task 落實設計決策「Matching：cosine similarity + tunable threshold」。Red tests 三條：highest-above-threshold 回 winning cluster id、all-below-threshold 回 None、空 dict 回 None，落實 `VoiceEnrollmentMatcher picks the highest-similarity cluster above threshold` requirement。

## 3. Repository 與 model

- [x] 3.1 [P] 在 `packages/backend/meeting_playbook/voice_enrollment/models.py` 定義 `VoiceEnrollment` SQLAlchemy model 對應 1.1 的 schema（user_id PK、sample_wav_path、embedding BYTEA、created_at TIMESTAMPTZ）。
- [x] 3.2 [P] 在 `packages/backend/meeting_playbook/voice_enrollment/repository.py` 實作 `VoiceEnrollmentRepository.get_for_user(user_id)` 與 `.upsert(user_id, wav_path, embedding)`：upsert 對既有 row 進行 in-place update；user delete 時 row 因 CASCADE 自動移除。Red tests 兩條：re-upload 不增加 row 數（仍 1 row）；delete user 後 voice_enrollment row 跟著消失，落實 `voice_enrollment table stores one embedding per user` requirement。

## 4. POST /api/voice_enrollment endpoint

- [x] 4.1 在 `packages/backend/meeting_playbook/voice_enrollment/router.py` 定義 FastAPI APIRouter，掛 `POST /api/voice_enrollment`：接 multipart wav、驗 content-type / size / duration（per 設計決策「30 秒上限與檔案驗證」）、把檔案存至 `VOICE_ENROLLMENT_DIR/{user_id}.wav`、呼叫 `compute_enrollment_embedding`、`upsert` row、回 `{enrolled_at}`；任何 validation 失敗回 HTTP 422 對應 error_code (`voice_enrollment.unsupported_format` / `too_large` / `too_long` / `invalid_sample`) 且**刪掉已暫存的 wav** 不留 orphan，落實 `POST /api/voice_enrollment uploads + replaces the per-user enrollment` requirement。
- [x] 4.2 在 `packages/backend/meeting_playbook/server.py` 註冊 `voice_enrollment_router`，確認在 X-User-Id 依賴鏈下取得 current user。Red tests 四條：valid sample → 200 + row written + wav on disk + embedding length % 4 == 0；re-enroll → row 數仍 1、created_at 更新；too_long → 422 且 wav 不留在磁碟；multi-speaker → 422 且 wav 不留在磁碟。

## 5. SingleChannelStrategy 暴露 DiarizeOutput

- [x] 5.1 在 `packages/backend/meeting_playbook/speaker/strategy.py` 給 `SingleChannelStrategy` 加 instance attribute `last_diarize_output: object | None`（default None），於 `assign_speakers` 結尾把當次 pipeline 的 `DiarizeOutput`（含 `speaker_embeddings`）與 label→cluster_id mapping 暫存到 attribute；DualChannelStrategy 無此 attribute。本 task 落實設計決策「Embedding 暴露問題：把 DiarizeOutput.speaker_embeddings 傳出 SingleChannelStrategy」。Red test：dual 跑完 `last_diarize_output` 不存在；single 跑完含非 None object 且能取到 `speaker_embeddings`。
- [x] 5.2 在 `packages/backend/meeting_playbook/speaker/pyannote_provider.py` 把原 `diarize(wav_path)` 改寫成回 `(segments, embeddings_by_label)`（或保留 segments 並把 embeddings 透過第二個方法/attribute 暴露），讓 single channel strategy 取得 `{cluster_id: embedding}` mapping；既有 8 個 pyannote_provider tests 不可破。

## 6. apply_speaker_attribution 整合 voice enrollment（voice-enrollment + meeting-session）

- [x] 6.1 擴 `packages/backend/meeting_playbook/speaker/finalize.py` 的 `apply_speaker_attribution` 簽名加 `voice_enrollment_repo`、`current_user_id`、`match_threshold` 參數；single-channel 路徑跑完 strategy 後若 enrollment 存在 → 取 strategy.last_diarize_output 算 cluster→embedding mapping → 呼叫 `VoiceEnrollmentMatcher.find_me_cluster` → 把 result chunks 內 `speaker == "speaker_cluster_<matched_id>"` 改寫為 `"me"`；DualChannelStrategy 路徑短路（不查 enrollment）。本 task 落實設計決策「Integration point：apply_speaker_attribution 後處理」並對應 `apply_speaker_attribution renames the matched single-channel cluster to me when an enrollment exists` requirement。
- [x] 6.2 Red tests for 6.1（在 `tests/speaker/test_finalize.py` 擴）：4 條情境逐一覆蓋 — (a) user 有 enrollment 且 cluster 2 上線 → 結果 chunk 1=`speaker_cluster_1`、chunk 2=`me`、chunk 3=`speaker_cluster_3`；(b) user 無 enrollment → 全 chunk 保留 cluster 標籤；(c) user 有 enrollment 但無 cluster 過 threshold → 全 chunk 保留 cluster 標籤；(d) dual-channel 永遠不 rename（即使 user 有 enrollment）；皆對應 `apply_speaker_attribution renames the matched single-channel cluster to me when an enrollment exists` requirement 的 4 個 scenario。
- [x] 6.3 在 `packages/backend/meeting_playbook/sessions/router.py` finalize 區段，把 voice_enrollment repo + 從 X-User-Id 取得的 user_id 傳進 `apply_speaker_attribution` 呼叫；既有 dual-channel router tests 0 regression（既 fixture / 既 mock 不需改），落實 `WebSocket message contract for the meeting session` 內 single-channel + enrollment 路徑。

## 7. /settings/voice 前端路由（voice-enrollment UI）

- [x] 7.1 在 `packages/web/src/routes/settings/voice.tsx` 實作 standalone route：用 `MediaRecorder` API 開 mic、30 秒 hard cutoff、即時 RMS 音量計、預聽 `<audio>` 元素、重錄按鈕、儲存按鈕；落實 `/settings/voice route lets the user record, preview, and save a 30-second voice sample` requirement 的 「Recording auto-stops at 30 seconds」 scenario。
- [x] 7.2 在 `packages/web/src/lib/voice-enrollment-api.ts` 包裝 `POST /api/voice_enrollment` 上傳 helper（multipart blob）；route 的儲存按鈕呼叫此 helper、成功顯示本地化「聲紋已儲存」/「Voice sample saved」、失敗透過 `localizedErrorMessage` 顯示對應錯誤，落實同 requirement 的「Save POSTs the recording and shows success confirmation」與「Server-side validation error surfaces localized message」scenarios。
- [x] 7.3 [P] 在 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json` 同步新增 settings.voice.* 命名空間（heading / hint / startRecording / stopRecording / preview / save / saved / errors.unsupportedFormat / errors.tooLarge / errors.tooLong / errors.invalidSample）；`bun --filter @meeting-playbook/web test` 跑 `locales.test.ts` deep-equal 通過。
- [x] 7.4 在 `packages/web/src/route-tree.tsx` 加 `/settings/voice` route 註冊（單獨頂層 route，不掛在尚未存在的 `/settings` shell 下）。
- [x] 7.5 寫 `packages/web/src/routes/settings/voice.test.tsx`：4 條 component test — (a) 點開始錄音後音量計出現；(b) 30 秒後自動停止、preview audio 出現、save 按鈕 enabled；(c) save 按下 POST 至 `/api/voice_enrollment`、回 200 後顯示「儲存成功」；(d) 模擬 422 `voice_enrollment.invalid_sample` 回覆 → 顯示本地化錯誤訊息且 save 按鈕仍 enabled，落實前述 3 個 scenario。

## 8. 領域語彙與設定文件

- [x] 8.1 更新 `CONTEXT.md` glossary 加「Voice enrollment sample (聲紋樣本)」一條（描述：使用者預錄一次的 30 秒 WAV，single-channel finalize 時用來把符合的 cluster 自動標 `me`）；驗證：`grep -F 'Voice enrollment sample' CONTEXT.md` 命中。

## 9. End-to-end + coverage

- [x] 9.1 新增 `tests/integration/test_voice_enrollment_e2e.py`：模擬 user POST enrollment → DB row 寫入 → 模擬 single-channel meeting finalize → 驗證 transcript_chunk 表內 cluster 對應 chunk 的 speaker 被 rename 為 `me`，其他 chunk 維持 `speaker_cluster_*`；同檔再跑「無 enrollment」分支驗證全 chunk 保留 cluster 標籤。
- [x] 9.2 跑覆蓋率 `uv run pytest --cov=meeting_playbook.voice_enrollment --cov=meeting_playbook.speaker.finalize --cov-report=term-missing`，確認 `voice_enrollment/*` 80%+；`speaker/finalize.py` 在本 slice 修改範圍 80%+。
