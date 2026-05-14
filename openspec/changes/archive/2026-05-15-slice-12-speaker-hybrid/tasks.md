## 1. 環境與相依設定

- [x] 1.1 在 `packages/backend/pyproject.toml` 新增 `pyannote.audio` 相依，跑 `uv sync` 後 `python -c "import pyannote.audio"` import 成功，驗證套件落地。**Apple Speech Framework 路徑刪除**（per Apple 無公開 diarization API；ADR-0029 改記）。
- [x] 1.2 在 `.env.example` 加入 `PYANNOTE_AUTH_TOKEN=` 條目，並於 `README.md` 「First-time setup」加入「3.5 取得 pyannote HF token」段落，驗證 `grep PYANNOTE_AUTH_TOKEN .env.example` 與 `grep pyannote README.md` 都有命中。

## 2. DiarizationProvider 介面與 pyannote impl（v1.1 唯一 diarization provider 為 pyannote）

- [x] 2.1 [P] 在 `packages/backend/meeting_playbook/speaker/diarization.py` 定義 `DiarizationSegment` frozen dataclass 與 `DiarizationProvider` ABC，**契約**為 `diarize(wav_path) -> list[DiarizationSegment]` 回傳依 `start_ms` 排序、無 overlap；以 `tests/speaker/test_diarization_protocol.py` 寫 protocol-level red test（fake impl + 順序與 overlap 驗證）後實作至綠燈，對應 `DiarizationProvider interface exposes diarize for single-channel audio` requirement。
- [x] 2.2 實作 `PyannoteProvider` 於 `packages/backend/meeting_playbook/speaker/pyannote_provider.py`，**行為**：首次 `diarize` 從 HF Hub 載 `pyannote/speaker-diarization-3.1` pipeline、後續呼叫複用；無 `PYANNOTE_AUTH_TOKEN` 時 raise `DiarizationProviderUnavailable`。Red test 用 patched loader 確認載入次數恰好一次 + missing token 路徑，對應 `PyannoteProvider implements DiarizationProvider via HuggingFace pretrained model` requirement。
- [x] 2.4 用「2–3 人 ~2-3 分鐘」單聲道 fixture（放於 `packages/backend/tests/speaker/fixtures/multi_speakers_zh.wav`；QuickTime 自錄：使用者講話 + 播放一段別人講話的影片，必要時換片做 3 人）跑 `PyannoteProvider.diarize`，驗收 **(a) 至少回 2 個 cluster_id；(b) segment 排序與非重疊符合 protocol 契約；(c) p95 latency 寫進臨時 `compare_diarization.md` 供 ADR-0029 引用**。本 task 完成的證據是 `pytest tests/speaker/test_pyannote_real_audio.py` 跑出 pass + latency 數據可被人讀。

## 3. SpeakerAttributionStrategy 介面與三個元件（Strategy interface 抽象層 + Speaker label 命名 `speaker_cluster_N`）

- [x] 3.1 [P] 在 `packages/backend/meeting_playbook/speaker/strategy.py` 定義 `SpeakerAttributionStrategy` ABC，**契約**為 `assign_speakers(recordings, chunks) -> list[TranscriptChunk]` 保留輸入順序、不 mutate input；以 `tests/speaker/test_strategy_protocol.py` 寫 ABC 與 immutability red test 後最小實作至綠燈，對應 `SpeakerAttributionStrategy interface assigns speaker labels to transcript chunks` requirement。
- [x] 3.2 [P] 實作 `DualChannelStrategy`，**行為**：dual-channel ASR pipeline 在 chunk 進來時已寫 `speaker="me"`（mic）或 `"counterparty"`（blackhole），strategy 驗證該值 ∈ `{"me","counterparty"}` 後回傳不可變的 chunk 副本；遇到其他值 raise `UnresolvableChunkStream`；`recordings` 參數不被 strategy 使用（其驗證在 `select_strategy` 完成）。先寫 me pass-through / counterparty pass-through / unexpected speaker raise 三條 red test，對應 `DualChannelStrategy validates pre-labeled binary speaker values from the dual-channel ASR pipeline` requirement。
- [x] 3.3 實作 `SingleChannelStrategy(provider, overlap_threshold_ms=250)`，**行為**：呼叫 `provider.diarize(...)`，依 chunk 時段與 diarization segment 的最大 overlap 決定 `cluster_id`，寫成 `speaker_cluster_{N}`；無對應 segment 時寫 `speaker_cluster_unknown`；最大 overlap 同分時取較晚的 segment。先寫含「同分 tie-break」與「無 overlap fallback」兩條 red test，對應 `SingleChannelStrategy assigns speaker_cluster_N labels via DiarizationProvider` requirement 與決策 *Speaker label 命名 `speaker_cluster_N`*。

## 4. select_strategy 與 invalid 配置處理（Strategy selection 寫在 pipeline 邊界）

- [x] 4.1 在 `packages/backend/meeting_playbook/speaker/strategy.py` 實作 `select_strategy(recordings)`，**行為**：兩筆 recording、stream 集合 = `{"blackhole","mic"}` 回 `DualChannelStrategy`；單筆 recording 回 `SingleChannelStrategy(default_provider)`；其餘 raise `InvalidSpeakerConfiguration`。Red tests 涵蓋四條情境（dual / single / 兩筆但 mismatched stream / 三筆），對應 `select_strategy chooses dual or single based on recording configuration` requirement。
- [x] 4.2 把 `select_strategy` 內 `_default_diarization_provider()` placeholder 改為**真的回 `PyannoteProvider` 實例**：有 `PYANNOTE_AUTH_TOKEN` → return `PyannoteProvider(token=...)`；無 token → raise `DiarizationProviderUnavailable` 並在訊息中指明 `PYANNOTE_AUTH_TOKEN` 缺失；落實 `PyannoteProvider is the single DiarizationProvider impl in v1.1` requirement。Red test 兩條：有 token 走 pyannote（type assertion）、無 token 走 fail-loud（`DiarizationProviderUnavailable` 拋出且訊息含環境變數名）。

## 5. Pipeline 邊界整合與 latency 預算（Diarization latency 預算）

- [x] 5.1 在 `packages/backend/meeting_playbook/sessions/runtime.py` 把既有 inline 的 BlackHole / mic 判斷移除，於 session finalize 路徑改呼叫 `select_strategy(...).assign_speakers(...)`，再寫入 DB；regression test `tests/sessions/test_finalize_dual.py` 確認 dual-channel 既有行為 100% 不變（既有 fixture 不需重錄）。
- [x] 5.2 在 single-channel finalize 路徑上量測 diarization 耗時，若超過 wav 長度的 0.3 倍 → `logger.warning("diarization_slow", ...)`，仍寫入結果（不阻擋 finalize）；新測 `tests/sessions/test_finalize_single_latency.py` 用 monkeypatch 的 slow provider 確認 warning 與寫入路徑兼具，對應決策 *Diarization latency 預算*。
- [x] 5.3 新增 `SPEAKER_HYBRID_ENABLED` env flag（default true），off 時 `select_strategy(...)` 強制走 `DualChannelStrategy` 並對 single-channel 配置 raise 既有錯誤；測試覆蓋 flag on / off 兩條路徑，作為 rollback 開關。

## 6. WebSocket 契約與錯誤處理（WebSocket message contract for the meeting session）

- [x] 6.1 修改 `packages/backend/meeting_playbook/sessions/messages.py` 中 transcript_chunk message 的 `speaker` 欄位 typing 為 `Literal["me","counterparty"] | str`（以正則 `^speaker_cluster_(\d+|unknown)$` 驗證 single-channel 值），落實 `WebSocket message contract for the meeting session` 對單聲道值域的擴充；單元測 `tests/sessions/test_messages.py` 加 single-channel emit 一條 chunk 驗證 schema 通過。
- [x] 6.2 在 session finalize 中捕捉 `InvalidSpeakerConfiguration`，emit `{"type":"error","error_code":"session.invalid_speaker_configuration"}` 後關閉 WS；新測 `tests/sessions/test_finalize_invalid_config.py` 用三筆 recording 觸發此路徑驗證 error frame 與 connection close。

## 7. ADR、領域語彙與設定文件

- [x] 7.1 撰寫 `docs/adr/0029-hybrid-speaker-attribution.md`，**內容契約**：明確 amend ADR-0016（不 supersede）；說明 v1.1 唯一 diarization provider 為 pyannote、AppleSpeech / 第三方 fallback / cloud provider 全部 defer 到未來 ADR；列 rationale。驗證：`grep -E '^- \*\*Status\*\*: Accepted' docs/adr/0029-*.md` + `grep -i 'amend.*ADR-0016' docs/adr/0029-*.md` 皆命中。
- [x] 7.2 更新 `CONTEXT.md`：在 domain glossary 加入「Single-channel mode (面對面模式)」與「Speaker cluster (與會者一/二/三...)」；non-goal 改寫成「Multi-speaker diarization 限制於 Single-channel mode；Dual-channel capture 仍為 binary」。`grep -F 'Single-channel mode' CONTEXT.md && grep -F 'Speaker cluster' CONTEXT.md && grep -F 'Multi-speaker diarization 限制於' CONTEXT.md` 皆命中。

## 8. 前端顯示 speaker_cluster_N（最小落地）

- [x] 8.1 在 `packages/web/src/components/transcript-pane.tsx` 加 `speaker_cluster_N` 與 `speaker_cluster_unknown` 兩種 case 的 label 解析；UI 顯示為 i18n key `transcript.speaker.cluster`（template `「與會者 {{n}}」` / `"Speaker {{n}}"`）與 `transcript.speaker.cluster_unknown`，並補 `zh-TW.json` + `en.json` 兩條字串；測試 `transcript-pane.test.tsx` 加 single-channel chunk render 一條快照確認顯示「與會者 1 / 與會者 2」。
- [x] 8.2 確認 `packages/web/src/locales/locales.test.ts` deep-equal 測試通過（雙 locale 鏡像）；本 task 的驗證即是 `bun --filter @meeting-playbook/web test` 通過。

## 9. End-to-end fixture 驗證

- [x] 9.1 新增 `tests/integration/test_single_channel_e2e.py`：用 Task 2.4 的 2–3 人 fixture 跑完整 finalize 路徑、檢查 DB 中 `transcript_chunk.speaker` 全為 `speaker_cluster_*` 且至少出現兩種 cluster id；同檔再跑既有 dual fixture 驗 `me` / `counterparty` 兩種值。本 task 完成等於 `uv run pytest tests/integration/test_single_channel_e2e.py -v` 全綠。
- [x] 9.2 跑全套測試覆蓋率：`uv run pytest --cov=meeting_playbook.speaker --cov-report=term-missing`，確認 `speaker/*` 80%+。（註：tasks 草稿原本提到 `sessions/runtime.py`，但 slice-12 實作把 finalize 邏輯放在 `speaker/finalize.py`，沒拆獨立的 runtime.py — coverage 落在 `speaker/finalize.py` 97%。）
