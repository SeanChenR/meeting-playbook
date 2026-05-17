## Context

S20a 已落地 meeting-level 附件的 schema / endpoint / dropzone UI。S20c 是把這條 input 通道接到 Playbook 生成器與 post-meeting summary 生成器，讓兩條既有 LLM 路徑改成 multimodal 呼叫。Tactical advisor 維持原 transcript-only 路徑（realtime 路徑加 multimodal 對 latency / cost 都是死刑）。

兩個生成器共用同一條 input pipeline 是這個 slice 的核心抽象：兩條 deep module（`AttachmentProcessor` 跟 `MultimodalContextBuilder`）讓 generator 端只接一個 well-typed 的 `MultimodalContext` 物件、不用各自處理 PDF / docx / image bytes 細節，而 staleness 判斷也統一走「附件集合 hash 比對 generation 時 snapshot」這個機制（沿用 slice-05 playbook + slice-10 summary 既有 `is_stale` 模式擴充一個新條件）。

## Goals / Non-Goals

**Goals**

- Playbook 生成器與 summary 生成器都能接受附件，餵進 Gemini 2.5 Pro multimodal call
- 兩條路徑共用同一條 input pipeline（`AttachmentProcessor` + `MultimodalContextBuilder`）避免邏輯雙寫
- 附件變動時生成過的 Playbook / summary 標 stale，UI 顯示 banner 提示重新生成
- TDD：input shape transformation 的 4 條主路徑（無附件 / 純圖 / 純 PDF / mix）table-driven 各別覆蓋
- 既有 generator API contract（七欄位 / 四節）100% 不破

**Non-Goals**

- Tactical advisor 走多模態 — 留 v1.2 brainstorm
- Image OCR — 圖直接以 bytes 餵 Gemini，不在我方抽文字
- Streaming Gemini cached content 優化（重複附件不上傳兩次）— 留 v1.2 brainstorm
- 任何附件 schema 變動（S20a 已凍結）
- Playbook / summary 自身 markdown contract 變動

## Decisions

### AttachmentProcessor 採 type-dispatched single-method 設計

`AttachmentProcessor.process(attachment_ref: AttachmentRef) -> ProcessedAttachment` 是唯一外部入口。內部依 `attachment_ref.kind` 走四條分支：

| `kind` | 處理方式 | 回傳形式 |
| --- | --- | --- |
| `image/jpeg`、`image/png`、`image/webp` | 直接 `Path.read_bytes()` + 計算 sha256 | `ProcessedAttachment(kind="image", mime=..., bytes=..., sha256=..., extracted_text=None)` |
| `application/pdf` | `pypdf.PdfReader(path).pages → "\n".join(page.extract_text())`，timeout `ATTACHMENT_TEXT_EXTRACTION_TIMEOUT_SECONDS` | `ProcessedAttachment(kind="text", mime=..., bytes=None, sha256=..., extracted_text="...")` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `docx.Document(path).paragraphs → "\n".join(...)` | 同上 |
| `text/plain`、`text/markdown` | `Path.read_text()` | 同上 |

任何 IO / 解析錯誤一律 raise `AttachmentProcessingError(error_code, attachment_id, cause)`。`error_code` 取自固定列表：`attachment.unsupported_kind` / `attachment.extraction_failed` / `attachment.extraction_timeout` / `attachment.too_large_to_process`。Generator 接到此例外的策略由 `MultimodalContextBuilder` 決定（見下）。

**Alternative considered**：依 kind 分四個獨立 class（`ImageProcessor`、`PdfProcessor`...）拿 DI 注入——被否決，介面太細碎、generator 端需要 keep 一張 dispatch 表，反而把 dispatch 邏輯外洩。Single class single method 配 ProcessedAttachment dataclass 是最薄抽象。

### MultimodalContextBuilder：固定順序、單筆 corrupt attachment 不擋整次生成

`MultimodalContextBuilder.build(text_context: str, attachments: list[AttachmentRef]) -> MultimodalContext` 回傳：

```
MultimodalContext(
    parts: list[ContentPart],          # 餵 google-genai client 的 contents
    snapshot_hash: str,                 # sha256(sorted(processed.sha256 for processed))
    skipped_attachment_ids: list[str], # 哪幾個附件因解析失敗被略過
)
```

`parts` 排序固定為「先所有圖片 → 再所有文字（PDF / docx / txt / md 抽出後） → 最後 system text_context」。這個順序讓 Gemini 先看視覺資料再看純文字脈絡，避免長 transcript 把 image 衝到 context window 邊緣。

單筆 corrupt 附件不擋整次生成：`build()` 對每個 attachment 呼叫 `AttachmentProcessor.process(...)`，若 raise `AttachmentProcessingError` 則 log warning + 把 attachment_id 加進 `skipped_attachment_ids`，繼續處理下一筆。Generator 拿到 `MultimodalContext` 之後可選擇是否把 skip list 帶進回傳值（v1 不帶；只用 log 觀察）。

**Alternative considered**：附件 SHA-256 直接 join 字串再 hash——被否決，順序不穩會導致 staleness 誤判；改成 sorted 之後再 join。**Alternative considered**：corrupt 附件直接 fail-fast 整次生成——被否決，使用者經常掛多份附件，一份壞掉就整次生成失敗是糟糕 UX；warning + skip 是合理 trade-off。

### Stale-tracking：附件集合 hash snapshot 寫進 playbook / summary row

`playbook` 與 `summary` 兩張 table 各加一欄 `attachment_hash_snapshot TEXT NULL`。生成成功時 generator 把 `MultimodalContext.snapshot_hash` 一併傳給 repository 的 `upsert(...)`，repository 同 row 一起寫入。`get_with_stale_flag(meeting_id)` 額外比一個條件：

```
current_snapshot = sha256(sorted(
    sha256(open(att.file_path,'rb').read())
    for att in MeetingAttachmentRepository.list_for_meeting(meeting_id)
    if att.deleted_at IS NULL
))
is_stale_from_attachments = (
    row.attachment_hash_snapshot != current_snapshot
)
is_stale = (existing_conditions) OR is_stale_from_attachments
```

無附件且 row.attachment_hash_snapshot 為 NULL → `current_snapshot` 也以「無附件」hash 表示（一致為 `sha256(b"") = e3b0...`），避免 NULL vs 空集合特例。

**Alternative considered**：另開 `attachment_snapshot` join table 紀錄生成當下的 attachment_id 集合與每筆 hash——被否決，新表跟新查詢成本不值得；single column TEXT 就足以判 stale。**Alternative considered**：用 attachments 的 `uploaded_at` 最大值——被否決，附件可被 delete 但 uploaded_at 不會減；hash 比對才能正確偵測 delete。

### Generator 邊界：PlaybookGenerator 顯式接 attachment_refs；Summarizer 自己查 repo

`PlaybookGenerator.generate(event_record, attachment_refs: list[AttachmentRef] = ())` 顯式收參數，由 calendar/router 層在呼叫前先 `MeetingAttachmentRepository.list_for_meeting(meeting_id)` 傳入。這條路徑歷史已有 calendar event input、由 router 控制 context 組裝，加一個顯式 list 最直觀。

`VertexProSummarizer.summarize(meeting_id)` 內部自己呼叫 `MeetingAttachmentRepository.list_for_meeting(meeting_id)`，因為其他 context（transcript / playbook / chat history）也都是 summarizer 自己 fetch（slice-10 既定模式）。維持「summarizer 統一 fetch」對稱。

**Alternative considered**：兩條都讓 router 傳——被否決，破壞 summarizer 既有 self-fetch 對稱。**Alternative considered**：兩條都讓 generator 內部 fetch——被否決，playbook generator 沒有 meeting_id（只有 calendar event），需要 router 補。

### Gemini multimodal call：用 google-genai 既有 `types.Part.from_bytes` + `types.Part.from_text`

兩個生成器都改成把 `MultimodalContext.parts` 直接餵 `client.models.generate_content(model=..., contents=parts, config=...)`。Image part 用 `Part.from_bytes(data=raw_bytes, mime_type="image/png")`，text part 用 `Part.from_text(text=...)`。System instruction 與 response schema 設定不變。

**Alternative considered**：用 Gemini Files API 預上傳附件取得 URI 再傳 reference——被否決，多一條外部 dependency + 需要 Files API 配額管理；inline bytes 對 5 檔 / 30MB 上限已足夠（單次 Gemini call < 35MB 在 limit 內）。

### TDD 四條主路徑 table-driven

`tests/attachments/test_multimodal_context.py` 用 pytest `@pytest.mark.parametrize` 四種輸入組合：

| Case | attachments | 預期 `parts` 結構 |
| --- | --- | --- |
| `no_attachments` | `[]` | 1 part：純 text |
| `single_image` | 1 個 PNG | 2 parts：image bytes part + text part |
| `single_pdf` | 1 個 PDF（mock pypdf 回 "abc"）| 1 part：text 內含「[Attachment: foo.pdf]\nabc」段落 |
| `mixed` | 1 PNG + 1 PDF + 1 docx | 2 parts：image part + text part（內含 PDF + docx 抽出文字、固定順序） |

四個 case 各自驗證 `snapshot_hash` 對相同 input 為 deterministic、對 input 順序 invariant、對附件變動敏感。

**Alternative considered**：四個獨立 test function——被否決，share fixture 跟 expected output 結構，parametrize 讓 diff readable。

## Implementation Contract

- **新模組 `packages/backend/meeting_playbook/attachments/`** 暴露：
  - `AttachmentProcessor.process(attachment_ref: AttachmentRef) -> ProcessedAttachment`。介面契約：image 類型回 `bytes is not None` 且 `extracted_text is None`；PDF / docx / txt / md 類型回 `extracted_text is not None` 且 `bytes is None`；任一處理錯誤 raise `AttachmentProcessingError`。
  - `MultimodalContextBuilder.build(text_context: str, attachments: list[AttachmentRef]) -> MultimodalContext`。介面契約：回 dataclass with `parts`（google-genai compatible `list[Part]`）、`snapshot_hash`（hex string）、`skipped_attachment_ids`（list[str]，可空）。順序保證：所有 image parts 在所有 text parts 之前，text_context 最後。
  - 自定例外 `AttachmentProcessingError(error_code: str, attachment_id: str, cause: Exception | None)`，error_code 取自 4 個固定值。
- **既有 `packages/backend/meeting_playbook/playbook_generation/generator.py`** 擴：
  - `PlaybookGenerator.generate(event_record, attachment_refs: Sequence[AttachmentRef] = ())` 新增第二參數。
  - 內部 build prompt 改成走 `MultimodalContextBuilder.build(text_context=existing_text_prompt, attachments=attachment_refs)`，把 `parts` 餵給 google-genai `generate_content`；structured-output schema 不變。
  - 回傳值除了既有七欄位 draft，新增 `attachment_hash_snapshot: str` 於同 dict（router 端傳到 repository upsert）。
- **既有 `packages/backend/meeting_playbook/playbook_management/repository.py`** 擴 `upsert_for_meeting(meeting_id, payload)`：payload 多認 optional key `attachment_hash_snapshot`，寫入新欄位；row schema 新增該 column。
- **既有 `packages/backend/meeting_playbook/playbook_management/repository.py`** 擴 `get_with_stale_flag`（若已存在；若 slice-10 only 在 summary 端有 → 也 mirror 給 playbook）：is_stale 計算多一條 attachment snapshot 比對。
- **既有 `packages/backend/meeting_playbook/summarization/vertex_summarizer.py`** 擴 `summarize(meeting_id)`：在既有 fetch 區段（transcript / playbook / chat）加 `attachments = await MeetingAttachmentRepository(session).list_for_meeting(meeting_id)`；傳給 `MultimodalContextBuilder.build(...)`；google-genai call 改用 `parts`；回 markdown + `attachment_hash_snapshot` 給 runtime 寫入。
- **既有 `packages/backend/meeting_playbook/summarization/repository.py`** 擴 `upsert(meeting_id, markdown, attachment_hash_snapshot)`、`get_with_stale_flag` 加 attachment 條件。
- **新 Alembic migration `0014_add_attachment_hash_snapshot.py`**：`ALTER TABLE playbook ADD COLUMN attachment_hash_snapshot TEXT NULL`、`ALTER TABLE summary ADD COLUMN attachment_hash_snapshot TEXT NULL`；down 是 drop column。
- **既有 `packages/web/src/components/playbook-pane.tsx`** 與 **`summary-pane.tsx`**：在 `is_stale === true` 時於 pane top 顯示 inline banner，文字走 i18n `playbook.stale.attachments_changed` / `summary.stale.attachments_changed`，按鈕呼叫既有 regenerate endpoint。
- **i18n**：雙 locale 加 `playbook.stale.attachments_changed` 與 `summary.stale.attachments_changed`；`locales.test.ts` deep-equal 通過。
- **`.env.example` + `config.py`**：加 `ATTACHMENT_TEXT_EXTRACTION_TIMEOUT_SECONDS=15`（int seconds）。
- **`pyproject.toml`**：加 `pypdf>=4.0` 與 `python-docx>=1.0`。

**Scope boundary** — In scope：attachments 模組、PlaybookGenerator 介面擴、VertexProSummarizer 介面擴、playbook & summary table 加 hash snapshot column、is_stale 邏輯擴、UI stale banner、i18n、pyproject 依賴、env var。Out of scope：tactical advisor 路徑、附件 schema 變動、Gemini Files API 採用、image OCR、Playbook 七欄位 / summary 四節 contract 變動。

## Risks / Trade-offs

- **PDF 抽文字失敗**（加密 / 損壞 / 純圖 PDF）→ `pypdf` raise → `AttachmentProcessor` 包成 `AttachmentProcessingError("attachment.extraction_failed", ...)` → builder skip 該附件並 log warning；usre 看到 banner 提示重新生成時，重新跑也會再 skip 同樣的 corrupt 檔；可接受但要在 docs/agents/playbook-generation.md 與 docs/agents/summarization.md 補一行 troubleshooting。
- **30MB 上限附件全圖檔**：5 個 5MB PNG → multimodal call payload ~30MB；google-genai inline payload 在合理範圍但實測 latency 可能拉長到 60s 邊界（playbook timeout）→ 對 timeout 留意，若多次觸發再評估 Files API。
- **附件集合 hash snapshot column 寫入時序**：generator 失敗時不能寫 row（既有 contract）；附件變動但生成失敗時下次 `is_stale` 仍會回 true（因為比對 row.snapshot vs 當前），UI 仍會顯示 banner，正確行為。
- **stale 判定誤判**：若使用者重新上傳同一份 PDF（內容 bytes 相同）→ hash 不變 → 不會標 stale → 不會多花一次生成；正向 trade-off。
- **multimodal call cost**：summary + playbook 每場 ≥ 2 次 Gemini Pro call、每次帶附件 → cost 上升；單人單機可接受，未來部署再評估 cached content。

## Migration Plan

- 跑 `alembic upgrade head` 加 `attachment_hash_snapshot` 欄位（NULLABLE 不影響既有 row）。
- 既有未掛附件的 playbook / summary row：`attachment_hash_snapshot IS NULL`；`get_with_stale_flag` 比對時把 NULL 視為「未紀錄附件狀態」→ 若當前附件集合 hash 為「空集合 hash」即視為一致；若當前有附件 → is_stale 從 attachment 條件為 true（合理：之前生成沒考慮附件，現在掛了應該重新跑）。
- Rollout：合主 branch 後在本地會議實測 1 場帶 PDF + 1 場帶 PNG，驗證 Gemini call 成功且 banner 行為正確。
- Rollback：alembic downgrade 1 步移除欄位；generator 端在 column 不存在時走「無 attachment_hash_snapshot」分支（讀寫 None 即可）。

## Open Questions

- pypdf 對 password-protected PDF 的行為（raise 還是回空字串）需要實測決定要 catch 哪個例外類型；apply 階段先 catch `Exception` 並 log 真正類別，1-2 個 trial 後 narrow 到具體 type。
- Gemini 2.5 Pro 對單次 30MB inline payload 是否有 latency 顯著影響？apply 階段測 1 個 mix case 後決定是否要在 docs/agents 留 caveat。
