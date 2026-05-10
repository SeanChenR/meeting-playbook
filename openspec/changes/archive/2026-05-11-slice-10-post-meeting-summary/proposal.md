- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/12
- PRD User Stories：https://github.com/SeanChenR/meeting-playbook/issues/1 (US #24, #25, #26, #28)

## Why

Slice 6/7 把整場 transcript 收齊；Slice 5 把 playbook 自動生成；Slice 8/9 把 in-meeting advisor + chat history 鋪好。會議結束時，所有 raw context 都在 DB 裡 — 缺的是「會後 30 秒內把對話濃縮成 markdown 摘要」這個 closing-the-loop 動作。本 slice = PRD 的第三條 lifecycle phase（會後 / Post-meeting），把 transcript + playbook + chat history 餵進 Gemini 2.5 Pro，產出 4 段 markdown（重點討論 / 決議 / Action items / 待解決問題），自動寫進 DB，detail page 開新 Tab 顯示，並提供匯出 .md 檔讓 Sean 寄出 / 存檔。

## What Changes

- 新表 `summary`（4 欄：id, meeting_id `UNIQUE` FK CASCADE, markdown, generated_at），1:1 關係，regenerate 用 `ON CONFLICT (meeting_id) DO UPDATE` upsert
- 新模組 `packages/backend/meeting_playbook/summarization/` 鏡像 `playbook_generation/` 結構：`MeetingSummarizer` Protocol + `VertexProSummarizer` impl + `prompts.py` (system instruction + user message builder) + `dependencies.py` (FastAPI singleton) + `repository.py` (`SummaryRepository`)
- Sessions router finalize block 在送完 `meeting_ended` 之後，**fire-and-forget** spawn 一個 background asyncio.Task 跑 `summarizer.summarize(meeting_id)`；不阻塞 WS close handshake
- 新 HTTP 端點：
  - `POST /api/meetings/{meeting_id}/summary` — 手動觸發 / 重新生成（idempotent upsert；busy 時回 409 `summary.busy`）
  - `GET /api/meetings/{meeting_id}/summary` — 拉當前 summary（沒有 → 404 `summary.not_found`；生成中 → 200 + `{status: "pending", generated_at: null}` 包裝）
- 詳情頁新增 **Tab 切換**：「Workspace」(既有三欄) + 「Summary」(新)；Summary tab 在 `meeting.status !== "completed"` 時 disabled + 「會議結束後可看摘要」hover 提示
- Summary tab 內容：
  - 上方狀態列：`生成於 {timestamp}` + 「重新生成」按鈕 + 「匯出 .md」按鈕
  - Stale 警示：當 `max(latest_transcript_chunk.created_at, playbook.updated_at, latest_chat_message.created_at) > summary.generated_at` 時顯示「⚠ 內容已更新，建議重新生成」
  - 主體：用既有 `<MarkdownPreview>` 渲染 4 個 section 的 markdown
  - Generation 中：skeleton + 「生成中⋯（約 30-60 秒）」hint
  - Generation 失敗：error 卡 + retry button
- Markdown export：File System Access API where supported；fallback blob download；filename = `{meeting.title}-{YYYY-MM-DD}.md`；內容 = summary markdown 本身（**不**包含 transcript / playbook / chat history）
- Prompt 結構（4 固定 sections，順序 frozen，empty 渲染 `(無)` / `(none)`）：
  1. `## 重點討論` / `## Key discussion points`
  2. `## 決議` / `## Decisions`
  3. `## Action items`（item 格式 `- [{owner_or_TBD}] {action}`）
  4. `## 待解決問題` / `## Open questions`
- Locale 從前端帶（zh-TW / en），與 advisor / playbook 同樣機制
- i18n 新 keys：`meetings.detail.tabs.{workspace, summary}`, `meetings.summary.{heading, generating, generatingHint, regenerate, exportMd, generatedAt, staleAlert, emptyState, sectionTitles.*}`, `errors.summary.{busy, not_found, generation_failed, generation_timeout}`

## Non-Goals

- 多人協作 / 評論 summary — read-only
- Summary 版本歷史 — upsert 直接覆蓋，不留舊版（YAGNI；個人 side project）
- Bundle export（summary + transcript + playbook 全包）— Sean 拍板只裝 summary
- Cancel-previous policy — 1-at-a-time per meeting；正在跑就 reject 409
- 即時更新 / live editing — 所有變更要按「重新生成」才生效
- 不同 LLM 供應商 — Vertex AI Gemini 2.5 Pro 唯一 provider
- Summary template 客製化 — 4 sections frozen
- 觸發條件擴展 — 只在 `meeting_ended` 之後 + 手動 POST，不支援 cron / 排程
- Action item 自動指派到外部系統（Asana / Linear etc.） — 純 markdown
- Tab UI 之外的 layout 選項 — 3 columns / stack 仍只在 Workspace tab 內生效
- Summary tab 在非 completed 狀態的「預覽」/「先看一下」— disabled 就是 disabled
- Schema 加 status / error_code 欄位 — 失敗的 generation 不寫 row（同 Slice 9 chat_message minimal-schema 哲學）；前端用 React Query state 管 in-flight

## Capabilities

### New Capabilities

- `meeting-summary`: post-meeting markdown summary 完整契約 — `summary` table + `MeetingSummarizer` Protocol + Vertex 2.5 Pro impl + 4-section prompt + auto-trigger 在 meeting_ended + manual POST endpoint + GET endpoint + concurrency policy（1-at-a-time per meeting）

### Modified Capabilities

- `meeting-detail-layout`: 詳情頁加入 Workspace / Summary 兩個 tab；Summary tab 在 status !== completed 時 disabled；Summary tab 內含 markdown render + regenerate + export + stale alert
- `meeting-session`: WS finalize block（slice-7 既有）在送 `meeting_ended` 之後 fire-and-forget spawn `summarizer.summarize(meeting_id)` background task；不阻塞 WS close

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0006_create_summary.py` — Alembic migration 建 `summary` 表 + UNIQUE constraint
  - `packages/backend/meeting_playbook/summarization/__init__.py`
  - `packages/backend/meeting_playbook/summarization/base.py` — `MeetingSummarizer` Protocol + `Summary` dataclass
  - `packages/backend/meeting_playbook/summarization/vertex_summarizer.py` — Vertex 2.5 Pro impl（async streaming + 90s timeout）
  - `packages/backend/meeting_playbook/summarization/prompts.py` — system instruction + user message builder（4 fixed sections）
  - `packages/backend/meeting_playbook/summarization/dependencies.py` — `get_meeting_summarizer_dependency` lru_cache singleton
  - `packages/backend/meeting_playbook/summarization/models.py` — `Summary` SQLAlchemy ORM
  - `packages/backend/meeting_playbook/summarization/repository.py` — `SummaryRepository.upsert / get_for_meeting / has_pending`
  - `packages/backend/meeting_playbook/summarization/router.py` — POST + GET endpoints
  - `packages/backend/meeting_playbook/summarization/runtime.py` — process-scoped in-flight registry（dict[meeting_id, asyncio.Task]）for busy-check + auto-trigger spawn
  - `packages/backend/tests/summarization/__init__.py`
  - `packages/backend/tests/summarization/test_prompts.py`
  - `packages/backend/tests/summarization/test_vertex_summarizer.py`
  - `packages/backend/tests/summarization/test_repository.py`
  - `packages/backend/tests/summarization/test_router.py`
  - `packages/backend/tests/summarization/test_runtime.py`
  - `packages/backend/tests/test_alembic_summary.py`
- 後端修改：
  - `packages/backend/meeting_playbook/sessions/router.py` — finalize block 之後 spawn `summarization.runtime.spawn_summary_task(meeting_id)`；不 await
  - `packages/backend/meeting_playbook/server.py` — mount `summarization.router`
  - `packages/backend/meeting_playbook/config.py` — 加 `vertex_pro_model_id: str = "gemini-2.5-pro"` setting（與 `vertex_flash_model_id` 對稱）
  - `packages/backend/tests/conftest.py` — truncate cascade 加 `summary`
- 前端新檔：
  - `packages/web/src/lib/summary-api.ts` — `summaryQueryOptions` (GET) + `regenerateSummary` (POST) + `SummaryApiError` envelope
  - `packages/web/src/lib/summary-api.test.ts`
  - `packages/web/src/lib/markdown-export.ts` — `exportSummaryAsMarkdown(meeting, markdown)` (File System Access + blob fallback)
  - `packages/web/src/lib/markdown-export.test.ts`
  - `packages/web/src/components/summary-pane.tsx` — Summary tab 主體
  - `packages/web/src/components/summary-pane.test.tsx`
  - `packages/web/src/hooks/use-detail-tab.ts` — tab state（localStorage persisted；workspace 預設）
  - `packages/web/src/hooks/use-detail-tab.test.tsx`
- 前端修改：
  - `packages/web/src/routes/meetings/detail.tsx` — 包進 Tabs UI；workspace tab 包既有三欄；summary tab 條件渲染 SummaryPane；Summary tab disabled when `status !== "completed"`
  - `packages/web/src/routes/meetings/detail.test.tsx` — Tab 切換 + summary tab gating + summary fetch hydration tests
  - `packages/web/src/components/ui/` — 加 `tabs.tsx`（shadcn Tabs primitive 若未存在）
  - `packages/web/src/locales/zh-TW.json` + `packages/web/src/locales/en.json` — 加 `meetings.detail.tabs.*`、`meetings.summary.*`、`errors.summary.*`
- 文件：
  - `docs/agents/summarization.md` — 新增 agent doc：MeetingSummarizer 架構、prompt 結構、auto-trigger 流程、in-flight registry concurrency 模式、export 行為
