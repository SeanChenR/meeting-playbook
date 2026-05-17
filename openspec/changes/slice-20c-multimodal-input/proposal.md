> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/28
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
> Depends on: slice-20a-meeting-attachment（必須先 archive 才能 apply 本 slice）

## Why

S20a 落地之後，使用者可以對會議掛 image / PDF / docx / txt / md 附件，但 Playbook 生成器與 post-meeting summary 生成器仍只看 Calendar metadata + transcript + chat，完全讀不到附件內容。使用者只能手動把 briefing 貼進 Playbook 編輯器，違反 PRD #16 的 user story 32 / 33。S20c 把附件納進兩個生成器的 Gemini multimodal context，並在生成後若附件變動時提示「過期 — 是否重新生成？」。Tactical advisor 維持低 latency 不動，明確 out of scope。

## What Changes

- 新增 `AttachmentProcessor`（deep module）：依檔案 MIME 抽出文字（PDF / docx）或回 raw bytes（image），並保留 SHA-256 hash 與 mtime 供 stale-tracking 使用
- 新增 `MultimodalContextBuilder`（deep module）：把 attachments + 文字 system context 組成 google-genai 的 `parts` 陣列；無附件 → 原始字串 prompt；圖檔 → inline `Part.from_bytes(mime_type=..., data=...)`；PDF / docx 抽出的文字 → 內嵌進 user message
- `PlaybookGenerator.generate(...)` 簽名擴一個可選 `attachment_refs: list[AttachmentRef]`，內部走 `MultimodalContextBuilder`；Gemini 2.5 Pro multimodal call 通道改成 `parts` array
- `VertexProSummarizer.summarize(meeting_id)` 內部去 `MeetingAttachmentRepository.list_for_meeting(meeting_id)`，把附件納入 prompt parts；維持原四節 markdown contract 不變
- 擴 `playbook` table 加 `attachment_hash_snapshot TEXT NULL`、擴 `summary` table 加 `attachment_hash_snapshot TEXT NULL`：生成時記錄當下所有附件 hash 的串接 hash；之後比對得知是否 stale
- `PlaybookRepository.get_with_stale_flag` 與 `SummaryRepository.get_with_stale_flag` 的 `is_stale` 計算邏輯擴：除既有 transcript / playbook / chat_message 變動條件外，再比對 `attachment_hash_snapshot` 與當下附件集合 hash 是否一致
- Meeting detail UI：playbook pane 與 summary pane 在 `is_stale === true` 時顯示 banner「附件已更新 — 重新生成 Playbook?」/「附件已更新 — 重新生成 Summary?」；點按鈕呼叫既有 regenerate endpoint
- 新增 i18n key `playbook.stale.attachments_changed` / `summary.stale.attachments_changed` 雙 locale
- 新增 env var `ATTACHMENT_TEXT_EXTRACTION_TIMEOUT_SECONDS`（default `15`）防止 corrupt PDF 卡住生成
- 加 Python 依賴 `pypdf` 與 `python-docx`（pyproject.toml + uv.lock）

## Non-Goals

- **Tactical advisor 不改**：realtime 路徑要維持低 latency，附件 multimodal call 太貴；advisor 仍只看 transcript + playbook 文字
- 不做 image OCR — 圖直接以 bytes 餵 Gemini multimodal，由模型自行讀；本 slice 不引入 Tesseract 或其他 OCR
- 不做附件版本歷史（uploaded → replaced 不留歷史；deleted 直接 drop）
- 不做 cross-meeting attachment 重用（一份 PDF 掛到另一個 meeting 仍是另一筆 row）
- 不調整附件 30 天 retention policy（S20a 已決，本 slice 不動）
- 不為 streaming Gemini 重新設計 prompt cache（v1.2 再評估 google-genai cached content）
- 不改 Playbook 七欄位的 schema 或 markdown contract，也不改 summary 四節結構
- 不替換 google-genai SDK — `Part.from_bytes` / `Part.from_text` 已支援 multimodal

## Capabilities

### New Capabilities

(none — 本 slice 不引入新 capability，所有變動 fold 進兩個既有生成器 capability)

### Modified Capabilities

- `playbook-generation`: 生成器多吃可選 `attachment_refs`；prompt 變成 google-genai `parts` 陣列；輸入 attachment 集合 hash 變動時 `is_stale = true`
- `meeting-summary`: summarizer 內部抓附件並納入 multimodal context；`get_with_stale_flag` 把 attachment hash 列入 staleness 條件；前端 summary pane 顯示「附件變動」stale 提示

## Impact

- Affected specs:
  - Modified: `openspec/specs/playbook-generation/spec.md`, `openspec/specs/meeting-summary/spec.md`
- Affected code:
  - New:
    - packages/backend/meeting_playbook/attachments/processor.py
    - packages/backend/meeting_playbook/attachments/multimodal_context.py
    - packages/backend/meeting_playbook/attachments/exceptions.py
    - packages/backend/tests/attachments/test_processor.py
    - packages/backend/tests/attachments/test_multimodal_context.py
    - packages/backend/tests/playbook_generation/test_generator_multimodal.py
    - packages/backend/tests/summarization/test_summarizer_multimodal.py
    - packages/backend/tests/integration/test_playbook_with_attachments.py
    - packages/backend/tests/integration/test_summary_with_attachments.py
    - packages/backend/alembic/versions/0014_add_attachment_hash_snapshot.py
  - Modified:
    - packages/backend/meeting_playbook/playbook_generation/generator.py
    - packages/backend/meeting_playbook/playbook_generation/prompts.py
    - packages/backend/meeting_playbook/playbook_management/repository.py
    - packages/backend/meeting_playbook/playbook_management/models.py
    - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
    - packages/backend/meeting_playbook/summarization/repository.py
    - packages/backend/meeting_playbook/summarization/models.py
    - packages/backend/meeting_playbook/summarization/prompts.py
    - packages/backend/meeting_playbook/config.py
    - packages/backend/pyproject.toml
    - packages/web/src/components/summary-pane.tsx
    - packages/web/src/components/playbook-pane.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - .env.example
  - Removed: (none)
