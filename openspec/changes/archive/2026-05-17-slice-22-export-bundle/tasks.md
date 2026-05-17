<!--
每個 task 必須說明「交付的行為 / 契約」以及「如何驗證完成」。檔案路徑只是
locator，不是 task 本身。
-->

## 1. Markdown 序列化純函式（meeting-export 基礎）

- [x] 1.1 [P] [AC-1] 實作 `playbook_to_markdown serializes the Playbook into a deterministic structure`：在 `packages/backend/meeting_playbook/export/markdown.py` 暴露純函式，行為遵循 design 章節「Markdown 序列化規則」— H1 為 meeting title、free_form_markdown 在前、6 個結構化 Playbook field 以固定順序輸出 H2、空欄位以 `_(empty)_` 佔位。驗證：`uv run pytest packages/backend/tests/export/test_markdown.py::test_playbook_markdown_emits_six_field_h2 packages/backend/tests/export/test_markdown.py::test_playbook_markdown_empty_field_placeholder` 兩條 red→green 通過。

- [x] 1.2 [P] [AC-2] 實作 `transcript_to_markdown renders TranscriptChunk rows with speaker label mapping`：在同一檔暴露純函式，行為遵循 design 章節「Markdown 序列化規則」— H1 為 `# Transcript`，每個 chunk 一行 `**[HH:MM:SS] {label}**: {text}`；speaker 為 `me` / `counterparty` / `speaker_cluster_N` 時分別映射為 `Me (我方)` / `Counterparty (對方)` / `與會者 N`，其他值原樣輸出。驗證：`uv run pytest packages/backend/tests/export/test_markdown.py::test_transcript_markdown_speaker_label_mapping packages/backend/tests/export/test_markdown.py::test_transcript_markdown_empty_list` 通過。

- [x] 1.3 [P] [AC-3] 實作 `summary_to_markdown passes the existing markdown through under an H1`：在同一檔暴露純函式，回傳 `# Summary\n\n{summary.markdown}\n`，遵循 design 章節「Markdown 序列化規則」對 summary 不做二次格式化的決策。驗證：`uv run pytest packages/backend/tests/export/test_markdown.py::test_summary_markdown_passes_through` 通過。

## 2. Bundler deep module（MeetingExportBundler 串流契約）

- [x] 2.1 [AC-4] 實作 `MeetingExportBundler streams a ZIP bundle for a single meeting`：在 `packages/backend/meeting_playbook/export/bundler.py` 暴露 `class MeetingExportBundler` 與 async method `iter_zip_chunks(meeting_id, user_id) -> AsyncIterator[bytes]`，內部組合 design 章節「Python stdlib zipfile + FastAPI StreamingResponse，不引第三方 streaming ZIP」+「串流推送策略：write_iter pattern with chunked WAV stdin」決策（`SpooledTemporaryFile(max_size=4 MiB)` + `zipfile.ZipFile(..., allowZip64=True)` + `chunked_wav_reader`）；越權或 meeting 不存在時 raise `MeetingNotFound`。驗證：`uv run pytest packages/backend/tests/export/test_bundler.py::test_bundler_includes_playbook_transcript_summary_when_summary_exists packages/backend/tests/export/test_bundler.py::test_bundler_raises_meeting_not_found_for_cross_user` 通過。

- [x] 2.2 [AC-5] `ZIP bundle excludes recordings whose Recording row is soft-deleted` 與 `Export bundle MUST exclude recordings whose Recording row is soft-deleted`（recording-retention 補強）：bundler 內 SQL 走 `WHERE meeting_id = :id AND deleted_at IS NULL`，落實 design 章節「Recording 過期判斷下推到 SQL，不做 file-exists 二次驗證」；過期 Recording 不出現在 ZIP，其他 artefact 仍存在。驗證：`uv run pytest packages/backend/tests/export/test_bundler.py::test_bundler_excludes_recording_when_deleted_at_set packages/backend/tests/export/test_bundler.py::test_bundler_excludes_all_recordings_when_all_expired` 通過。

- [x] 2.3 [AC-6] `Bundler skips summary.md when no Summary row exists`：bundler 在 SummaryRepository 回 None 時不寫 `summary.md`、不拋例外；playbook + transcript 仍寫入；落實 design 章節「Markdown 序列化規則」對 summary 缺席的對應。驗證：`uv run pytest packages/backend/tests/export/test_bundler.py::test_bundler_skips_summary_when_no_summary_row` 通過。

- [x] 2.4 [AC-7] 大檔記憶體上限驗證（confirm「串流推送策略：write_iter pattern with chunked WAV stdin」+「1 MiB chunk 寫死成常數，不暴露成 env var」常數選擇）：建立 200 MiB fixture WAV，跑完整 bundler；用 `tracemalloc.get_traced_memory()` 量 peak heap delta 必須 < 20 MiB；對應 spec scenario「Bundler refuses to materialize a large WAV in memory」。驗證：`uv run pytest packages/backend/tests/export/test_bundler.py::test_bundler_streams_wav_without_loading_full_file` 通過。

## 3. FastAPI 端點與 router 註冊

- [x] 3.1 [AC-8] 實作 `GET /api/meetings/{id}/export streams a ZIP with RFC 5987 Content-Disposition`：在 `packages/backend/meeting_playbook/export/router.py` 定義 `APIRouter`，掛 `GET /api/meetings/{meeting_id}/export`，依 design 章節「跨用戶授權與既有 Meeting ownership 一致」reuse `MeetingRepository.get_for_user`；成功回 `StreamingResponse(bundler.iter_zip_chunks(...), media_type="application/zip")` + 由 design 章節「ZIP filename 規則 + Content-Disposition」決定的雙值 header（`filename="<ascii>"` + `filename*=UTF-8''<percent>`）；越權回 404 `meeting.not_found`。驗證：`uv run pytest packages/backend/tests/export/test_router.py::test_export_endpoint_returns_zip_with_correct_disposition packages/backend/tests/export/test_router.py::test_export_endpoint_returns_404_for_other_users_meeting` 通過。

- [x] 3.2 在 `packages/backend/meeting_playbook/server.py` 註冊 `export_router`；確認 `X-User-Id` header 在 dependency chain 中被讀到（落實 spec scenario「Missing X-User-Id header is rejected per auth-gateway contract」）。驗證：`uv run pytest packages/backend/tests/export/test_router.py::test_export_endpoint_rejects_missing_x_user_id` 通過，且既有 `tests/meetings/test_endpoints.py` 0 regression。

## 4. 前端按鈕、API helper 與 i18n

- [x] 4.1 [AC-9] [P] 實作 `Export i18n strings exist in both locale files`：在 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json` 同步加入 `meetings.detail.export`（`匯出` / `Export`）、`meetings.detail.exporting`（`匯出中…` / `Exporting…`）、`meetings.detail.exportFailed`（`匯出失敗` / `Export failed`）三組 key。驗證：`bun --filter @meeting-playbook/web test packages/web/src/locales/locales.test.ts` 通過（deep-equal 兩個 locale 對齊）。

- [x] 4.2 [P] 在 `packages/web/src/lib/export-api.ts` 實作 `exportMeeting(meetingId, expectedFilename)` helper：行為 = `fetch('/api/meetings/{id}/export')` → 讀 Blob → `URL.createObjectURL` + 隱藏 `<a download>` 觸發下載 → revoke URL；失敗時 throw `MeetingApiError`（重用 meetings-api 既有錯誤型別），落實 design 章節「ZIP filename 規則 + Content-Disposition」對前端的接收契約。驗證：`bun --filter @meeting-playbook/web test packages/web/src/lib/export-api.test.ts` 通過（mock fetch 回 200/Blob + 觸發 download 一次）。

- [x] 4.3 [AC-10] 實作 `Frontend meeting detail exposes an Export button that triggers a browser download`：在 `packages/web/src/components/export-meeting-button.tsx` 暴露按鈕元件，使用 `t("meetings.detail.export")`；按下時呼叫 `exportMeeting` helper，期間 button disabled + spinner；錯誤時透過 `localizedErrorMessage` 顯示 toast；在 `packages/web/src/routes/meetings/detail.tsx` 的 `MetadataCard` 區掛入。驗證：`bun --filter @meeting-playbook/web test packages/web/src/components/export-meeting-button.test.tsx` 通過 4 條：renders by locale / disables during fetch / triggers `<a download>` on 200 / shows localized toast on 404。

## 5. End-to-end 與覆蓋率

- [x] 5.1 端對端整合驗證：建一場含 Playbook + 3 chunks + Summary + 2 Recording（一個 `deleted_at IS NULL`、一個 NOT NULL）的 fixture meeting，呼叫 `GET /api/meetings/{id}/export`，把 streaming response 寫入暫存檔，用 `zipfile.ZipFile` 重新讀回 namelist + 各 entry 內容；assert namelist = `{playbook.md, transcript.md, summary.md, recordings/<未過期 stream>.wav}`、Content-Disposition 雙值正確、過期 stream WAV 不在 namelist；同時跑「無 summary」與「全 recording 過期」兩條 branch。驗證：`uv run pytest packages/backend/tests/export/test_router.py::test_export_endpoint_end_to_end_bundle_shape` 通過。

- [x] 5.2 跑覆蓋率 `uv run pytest --cov=meeting_playbook.export --cov-report=term-missing`；確認 `meeting_playbook/export/*` ≥ 80% line coverage。驗證：執行該指令並 `grep "TOTAL"` 顯示 export module ≥ 80%。

- [x] 5.3 確認 GitHub Issue https://github.com/SeanChenR/meeting-playbook/issues/23 全部 acceptance criteria 已在 spec / 測試覆蓋並回填到 Issue 留言。驗證：Issue 內 6 個 acceptance checkbox 全打勾並有對應 test / spec scenario 連結。
