## Context

Slice 5 把 PlaybookGenerator + Vertex 2.5 Pro 模式建好；Slice 6/7 把整場 transcript 收齊；Slice 8/9 把 in-meeting advisor + chat history 鋪好。Lifecycle 三段裡（會前 / 會中 / 會後）只剩 **會後** 沒做。

**現有可重用設施**:
- `playbook_generation/generator.py` — Vertex 2.5 Pro async wrapper + 60s timeout + JSON-schema fallback（`_default_call_model` + `genai.Client(vertexai=True, ...)`），exact precedent for Slice 10
- `playbook_generation/prompts.py` — system + user message builder pattern
- `sessions/router.py:469` (finalize block) — meeting status → `completed` + `meeting_ended` 送出的位置，是 auto-trigger 的天然 hook
- `sessions/repository.py::list_chunks_for_meeting` — 拉整場 transcript（slice 6 已存在）
- `playbooks/repository.py::get_or_create_for_meeting` — 拉 playbook（slice 4 已存在）
- `chat/repository.py::list_for_meeting` — 拉 chat history（slice 9 已存在）
- `meeting_playbook/config.py` — 已有 `vertex_flash_model_id`；本 slice 對稱加 `vertex_pro_model_id`
- `meetings/dependencies.py::get_session_factory_dependency` — 開新 AsyncSession 給 background task 用，slice 8 既有

整個設施齊備 — 本 slice 是把現有模組「橫向接起來」+ 加 markdown export + Tab UI。

**用戶價值**：會議結束後 30-60 秒內，Sean 不用手動整理筆記就有 markdown 摘要，可直接寄出 / 存檔 / 貼入下一場會議的 playbook。PRD US #24/25/26 + #28 直接對應。

## Goals / Non-Goals

**Goals:**

- 會議結束 → 自動生成 4 段 markdown 摘要寫進 DB；UI Tab 顯示
- 提供「重新生成」+「匯出 .md」兩個用戶動作
- 內容 stale 時主動提示重新生成
- Auto-trigger 不阻塞 WS close handshake（user 立刻看到「結束」狀態）
- 共用 Vertex client / config / repo dependency injection 模式（不新增 SDK 依賴）

**Non-Goals:**

- Summary 版本歷史 / multi-revision — 直接 upsert 覆蓋
- Cancel-previous policy — 1-at-a-time per meeting，busy 時 reject
- Edit / 評論 / 多人協作 — read-only
- Bundle export（summary + transcript + playbook）— Sean 拍板只裝 summary
- 其他 LLM provider — Vertex AI 唯一
- Status / error_code 欄位 — minimal schema
- Auto-trigger 之外的觸發條件 — 不支援 cron / 排程 / 條件觸發
- Action item 跨系統指派 — 純 markdown
- Tab 之外的 UI surface — Summary 專屬一個 tab

## Decisions

### Decision 1: Schema 4 欄 + UNIQUE on meeting_id（1:1 關係）

```sql
CREATE TABLE summary (
  id            TEXT PRIMARY KEY,                                        -- sm_<token>
  meeting_id    TEXT NOT NULL UNIQUE REFERENCES meeting(id) ON DELETE CASCADE,
  markdown      TEXT NOT NULL,
  generated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Rationale**: PRD Issue #12 acceptance criteria 明確列 4 欄。`UNIQUE (meeting_id)` 表示 1:1，regenerate 用 `INSERT ... ON CONFLICT (meeting_id) DO UPDATE SET markdown = EXCLUDED.markdown, generated_at = now()` upsert，不留歷史版本（YAGNI）。沒有 status / error_code — 失敗的 generation 不寫 row（同 Slice 9 chat_message 哲學），前端用 React Query state 管 in-flight。

**Alternatives considered**:
- A: 加 status enum (`pending`/`done`/`failed`) + version int → schema 複雜，前端要分 4 種 UI 狀態，YAGNI
- B: 採用 (這次)：純結果表 + minimal schema

### Decision 2: Auto-trigger 用 fire-and-forget background task

WS finalize 流程結束、`meeting_ended` 已送出、WS 已 close 之後，**在 router handler 結束前** 呼叫 `summarization.runtime.spawn_summary_task(meeting_id)`。這個 helper 內部 `asyncio.create_task(...)` 把 task 註冊到一個 process-scoped 字典 `_inflight: dict[str, asyncio.Task]`，不 await。

```
[user 按 End] → end_meeting WS → finalize block → status=completed →
meeting_ended 送出 → spawn_summary_task() → router 結束、WS close
                                                      ↓
                              (背景) summarizer.summarize() runs ~30-60s
                                                      ↓
                                       SummaryRepository.upsert(...)
                                                      ↓
                                       _inflight.pop(meeting_id)
```

User 重新整理或開 Summary tab → GET /summary → 拿到結果（or `pending` if still in-flight）。

**Rationale**: Vertex 2.5 Pro 90s timeout，同步阻塞 WS close 會讓 user 看 UI hang 一分鐘。Fire-and-forget 讓 user 感覺「立刻結束」，summary 用拉的方式 hydrate（slice 9 chat_messages 同模式）。

**Alternatives considered**:
- A: 同步在 finalize block 內 `await summarizer.summarize(...)` → user 看 hang 60s → 爛體驗
- B (採用)：fire-and-forget background + UI poll
- C: WebSocket push `summary_done` frame → 多一條 protocol，且 user 通常已關 WS（離開 detail page），不划算

### Decision 3: In-flight registry 用 process-scoped dict（不 DB）

`summarization/runtime.py`：

```python
_inflight: dict[str, asyncio.Task[None]] = {}
_lock = asyncio.Lock()

async def spawn_summary_task(meeting_id: str) -> bool:
    """Returns True if spawned; False if one is already in-flight."""
    async with _lock:
        existing = _inflight.get(meeting_id)
        if existing is not None and not existing.done():
            return False
        task = asyncio.create_task(_run(meeting_id), name=f"summary-{meeting_id}")
        _inflight[meeting_id] = task
        return True

def is_pending(meeting_id: str) -> bool:
    task = _inflight.get(meeting_id)
    return task is not None and not task.done()
```

POST /summary endpoint 也走 `spawn_summary_task`；busy 時 reject 409 `summary.busy`。GET /summary 在 row 不存在但 in-flight 時回 200 + `{status: "pending"}`。

**Rationale**: 個人 side project 單機 single-process — 不需要 DB-level lock。Process restart 會丟掉 in-flight 狀態，但 task 也跟著掛掉，DB 沒寫 row → 前端下次 GET 看到「沒 summary，可重新生成」，state 一致。

**Alternatives considered**:
- A: DB lock table（advisory lock）→ 要管理 expiry / cleanup → 過設計
- B (採用)：in-memory dict
- C: 用 `summary` 表加 status 欄位 → 重新走 Slice 8 status-tracking 路徑，違反 Decision 1

### Decision 4: GET /summary 三態回應（present / pending / not_found）

```
GET /api/meetings/{id}/summary

# 已有 summary row：
200 { id, meeting_id, markdown, generated_at, is_stale: bool }

# 沒 row 但 in-flight：
200 { status: "pending", generated_at: null }

# 沒 row 且非 in-flight：
404 { error_code: "summary.not_found", message: "..." }
```

`is_stale` 欄位由 backend 計算（`max(latest_chunk.created_at, playbook.updated_at, latest_chat.created_at) > summary.generated_at`），前端不需要再算。

**Rationale**: 前端 React Query 的 success state 統一用 200，pending / done 走 status 欄位區分；not_found 用 404 是 conventional REST。is_stale 在 backend 算可以一個 SQL 查完，前端不需要拉 transcript / playbook / chat 的 timestamp。

**Alternatives considered**:
- A: pending 用 202 → React Query 預設不認 202 為 success，前端要特別處理
- B (採用)：三態統一 200/404
- C: 開 SSE / WS push → 過設計，individual side project

### Decision 5: Prompt 結構 — 4 fixed sections + locale-aware

System instruction (zh-TW)：

```
You are Sean's post-meeting note-taker.
你的任務是把整場會議的 transcript + Sean 準備的 playbook + 會中與 advisor 的對話，
濃縮成 4 段 markdown，順序與標題嚴格如下：

## 重點討論
列出 3-7 條 bullet，每條一個重點。

## 決議
列出本場做出的明確決定。沒有則寫 (無)。

## Action items
每條格式：- [{owner_or_TBD}] {action}
owner 從 transcript 中明確指派的人名抽取（"Sean 你..."、"請林經理..."）；
無法判斷者填 TBD。

## 待解決問題
列出本場提出但未解決的問題。沒有則寫 (無)。

絕對不要：
- 改變 4 個 heading 的文字 / 順序
- 跳過任何一個 section（empty 寫 "(無)"）
- 引入 transcript / playbook / chat history 之外的事實
- 加入 ## 摘要、## 總結 之類的多餘 heading
- 把 4 個 section 揉在一起寫成段落

請用繁體中文回答。
```

User message：
```
## 會議基本資料
- 標題：{meeting.title}
- 對方：{counterparty_display_name}
- 我方：{me_display_name}

## Playbook
{non-empty fields rendered as `## {field_name}\n{value}` + free_form_markdown if any}

## 整場 Transcript
{me_display_name}：{text} (HH:MM:SS)
{counterparty_display_name}：... (HH:MM:SS)
... (按 started_at ASC 全部)

## In-meeting Advisor 對話
（slice 9 chat_history, 按 created_at ASC; 空則 (無)）
{me_display_name}: {content}
Advisor: {content}
...
```

en locale system instruction 平行對應（heading 文字 → "Key discussion points / Decisions / Action items / Open questions"）。

**Rationale**: 4-section 順序 frozen 是 Issue #12 acceptance criteria 的明確要求（「contains the four required sections, even if a section is empty (renders as "(none)")」）。Owner extraction 用 LLM 判斷而不寫死 regex — transcript 多語混雜（Sean / 林經理 / @colleague）寫死 regex 易錯。

**Alternatives considered**:
- A: response_schema JSON 強制四欄 → JSON 沒 markdown 表達力，bullet / nested list 難寫
- B (採用)：純 markdown + system instruction 強制格式
- C: 兩階段：先 JSON 結構化 → 再 LLM 渲染 markdown → 兩次 LLM call 成本翻倍 + 延遲倍增

### Decision 6: UI Tab — Workspace 預設、Summary 在 status=completed 才 enabled

詳情頁包進 shadcn Tabs primitive：

```tsx
<Tabs value={tab} onValueChange={setTab}>
  <TabsList>
    <TabsTrigger value="workspace">{t("meetings.detail.tabs.workspace")}</TabsTrigger>
    <TabsTrigger value="summary" disabled={meeting.status !== "completed"}
                 title={meeting.status !== "completed" ? t("meetings.summary.disabledHint") : undefined}>
      {t("meetings.detail.tabs.summary")}
    </TabsTrigger>
  </TabsList>
  <TabsContent value="workspace">{/* 既有三欄 */}</TabsContent>
  <TabsContent value="summary">{meeting.status === "completed" && <SummaryPane meetingId={meetingId} />}</TabsContent>
</Tabs>
```

Tab 預設 `workspace`，state 持久化到 localStorage（`useDetailTab(meetingId)` hook）。Summary tab disabled 時 hover 提示「會議結束後可看摘要」。`<SummaryPane>` 只在 active tab 時 mount 避免無謂 GET（React Query staleTime 5 min）。

**Rationale**: Tab 切換比加第 4 區塊乾淨 — 三欄 workspace 在會議進行時是密集的工作介面，summary 是會後總結，兩者用戶心智狀態不同。Disabled tab 比隱藏好（user 知道有功能在等）。

**Alternatives considered**:
- A: 第 4 個區塊堆在三欄下方 → 會議進行中也看得到空 summary，視覺干擾
- B (採用)：Tab 切換
- C: 開新 route `/meetings/{id}/summary` → 多一層 navigation step，URL 也要設計

### Decision 7: Markdown export — File System Access API + blob fallback

```typescript
async function exportSummaryAsMarkdown(meeting: Meeting, markdown: string): Promise<void> {
  const filename = `${meeting.title}-${meeting.created_at.slice(0, 10)}.md`.replace(/[/\\:*?"<>|]/g, "_");
  if ("showSaveFilePicker" in window) {
    try {
      const handle = await (window as any).showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: "Markdown", accept: { "text/markdown": [".md"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(markdown);
      await writable.close();
      return;
    } catch (err) {
      // user cancelled or permission denied — fall through to blob fallback
      if ((err as DOMException)?.name === "AbortError") return;
    }
  }
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

Filename 用 meeting title + 建立日期；title 內非法字元（path separators、Windows reserved）替換成 `_`。

**Rationale**: File System Access API 是 Chrome / Edge 124+ 的標準，給 user「真的存到指定路徑」體驗；其他瀏覽器（Firefox / Safari）用 blob download 退回標準下載夾。`AbortError` 是 user 主動 cancel save dialog，不該 fallback；其他 error 才 fallback。

### Decision 8: SummaryRepository concurrency / transaction boundaries

```python
class SummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_meeting(self, meeting_id: str) -> Summary | None:
        result = await self._session.execute(
            select(Summary).where(Summary.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, *, meeting_id: str, markdown: str) -> Summary:
        now = datetime.now(UTC)
        new_id = f"sm_{secrets.token_urlsafe(16)}"
        stmt = (
            pg_insert(Summary)
            .values(id=new_id, meeting_id=meeting_id, markdown=markdown, generated_at=now)
            .on_conflict_do_update(
                index_elements=["meeting_id"],
                set_={"markdown": markdown, "generated_at": now},
            )
            .returning(Summary)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()
```

Background task 開新 AsyncSession（`session_factory()`）— 不跟 WS handler 的 request-scoped session 共用（WS 已 close，session 已釋放）。

**Rationale**: 同 Slice 8 / 9 的 separate-AsyncSession 模式 — background task 跟 request lifecycle 解耦。upsert 用 PostgreSQL 原生 `ON CONFLICT` 一個 SQL 完成，避免 race。

### Decision 9: Stale 判定 — backend 算，前端只渲染 boolean

GET /summary 的 SQL：

```sql
SELECT
  s.id, s.meeting_id, s.markdown, s.generated_at,
  (
    s.generated_at < COALESCE(
      (SELECT MAX(created_at) FROM transcript_chunk WHERE meeting_id = s.meeting_id),
      '-infinity'::timestamptz
    )
    OR s.generated_at < COALESCE(
      (SELECT updated_at FROM playbook WHERE meeting_id = s.meeting_id),
      '-infinity'::timestamptz
    )
    OR s.generated_at < COALESCE(
      (SELECT MAX(created_at) FROM chat_message WHERE meeting_id = s.meeting_id),
      '-infinity'::timestamptz
    )
  ) AS is_stale
FROM summary s
WHERE s.meeting_id = $1
```

Repository expose `get_with_stale_flag(meeting_id) -> SummaryWithStale | None`。前端只需 render `if (data.is_stale) <Alert>...</Alert>`。

**Rationale**: 集中在 backend 一個 SQL；前端不用拉三個 endpoint 算 timestamp 比較。`COALESCE(..., '-infinity')` 處理 transcript / playbook / chat 為空的情境（永遠不算 stale）。

## Implementation Contract

### Behavior contract

1. **Auto-trigger**: 當 WS 的 `_client_listener` 收到 `EndMeetingMessage` 並走完 finalize 流程（meeting status → completed、`meeting_ended` 已送出、WS 已準備關閉），router handler 在 return 前呼叫 `summarization.runtime.spawn_summary_task(meeting_id)`。Spawn 是 fire-and-forget — 不 await，不阻塞 router handler 的 return。
2. **Manual regenerate**: `POST /api/meetings/{meeting_id}/summary` 走同一個 `spawn_summary_task`；in-flight 時回 HTTP 409 with `{error_code: "summary.busy"}`；非 owner 回 404 `meeting.not_found`；成功觸發回 202 `{status: "pending"}`。
3. **Get summary**: `GET /api/meetings/{meeting_id}/summary` 三態：(a) 有 row → 200 + `{id, meeting_id, markdown, generated_at, is_stale}`；(b) 無 row 但 in-flight → 200 + `{status: "pending", generated_at: null}`；(c) 無 row 且非 in-flight → 404 `summary.not_found`。
4. **Generation**: `summarizer.summarize(meeting_id)` 開新 AsyncSession 拉 transcript + playbook + chat history → 組 prompt → call Vertex 2.5 Pro（90s outer timeout）→ 取得整段 markdown → 驗證有 4 個固定 heading → upsert into `summary`。失敗（timeout / quota / auth / heading 驗證失敗）不寫 row + log exception；in-flight registry pop 該 meeting_id。
5. **UI Tab**: 詳情頁 Workspace tab 預設 active；Summary tab 在 `meeting.status !== "completed"` 時 disabled + hover 提示。Summary tab content 用 React Query 拉 `summaryQueryOptions`，pending 時顯示 skeleton + 「生成中⋯（約 30-60 秒）」hint，一秒一次 refetch（pending 時）；done 時 markdown 渲染 + 操作列；is_stale=true 時 markdown 上方顯示 stale alert。
6. **Regenerate**: 用戶按「重新生成」→ POST → 成功 202 後 invalidate React Query cache → 進 pending 渲染 → polling 直到 done。
7. **Export**: 用戶按「匯出 .md」→ 呼叫 `exportSummaryAsMarkdown`；File System Access API supported → 開原生 save dialog；不支援 → blob 下載。Filename = `{meeting.title 移除非法字元}-{YYYY-MM-DD}.md`。Cancel save dialog 不 fallback。

### Data shapes

Summary TS:
```typescript
type Summary = {
  id: string;                  // sm_xxx
  meeting_id: string;
  markdown: string;
  generated_at: string;        // ISO-8601
  is_stale: boolean;
};

type SummaryPending = {
  status: "pending";
  generated_at: null;
};

type SummaryResponse = Summary | SummaryPending;
```

POST /summary response: `202 { status: "pending" }` | `409 { error_code: "summary.busy", message }` | `404 meeting.not_found`.

GET /summary response: `200 Summary` | `200 SummaryPending` | `404 summary.not_found`.

Markdown 4-section 結構（zh-TW；en 對應翻譯）：
```markdown
## 重點討論
- ...
## 決議
- ...（沒有則 "(無)"）
## Action items
- [Sean] ...
- [TBD] ...
## 待解決問題
- ...（沒有則 "(無)"）
```

### Failure modes

- **Vertex timeout (90s)**: `asyncio.TimeoutError` → log warning + skip upsert + pop _inflight；前端下次 GET 看到 `not_found` → 顯示「生成失敗，可重試」UI
- **Vertex quota / auth**: 同上 — 不寫 row + log exception + pop _inflight
- **4-heading 驗證失敗**（LLM 偏離格式）: 認定 generation failed → 不寫 row + log + pop _inflight
- **DB upsert failure**: log exception + pop _inflight；前端下次 GET 看到 `not_found`
- **Process restart 中途**: in-flight task 隨 process 死，DB 沒寫 row，_inflight dict 清空 → 前端下次 GET 看到 `not_found` → 用戶可重新觸發
- **Concurrent regenerate**: in-flight registry 擋第二個觸發 → POST 回 409 `summary.busy`；UI 把 regenerate button disabled 到 GET 拿到 done

### Acceptance criteria

- 後端 `pytest packages/backend` 全綠（含新 summarization / migration / router-spawn / runtime tests）
- 前端 `bun test packages/web` 無新失敗（slice-9 既有 8 baseline 失敗保留）
- locale parity guard 過
- Manual smoke-test by Sean: 開 meeting → in_progress → 講幾句 → end → 切到 Summary tab → 30-60s 內看到 4 段 markdown → 按「匯出 .md」→ 檔案存到桌面 → 內容對應 → 改 playbook → 重整 Summary tab → 看到 stale alert → 按「重新生成」→ 新版內容出現

### Scope boundaries (in / out)

**In scope**:
- `summary` table + Alembic migration
- `summarization/` 整個模組（base / vertex / prompts / dependencies / models / repository / router / runtime）
- WS finalize spawn
- POST + GET endpoints
- SummaryPane + Tabs UI 整合
- Markdown export (File System Access + blob fallback)
- Stale 判定 SQL + UI alert
- i18n 鍵
- 既有 detail.tsx 既有 layout 包進 Workspace tab（既有 columns / stack 切換不變）

**Out of scope**:
- 多 LLM provider 支援
- Summary 版本歷史
- Edit / 評論 summary
- Cancel-previous policy（採 1-at-a-time + busy reject）
- Bundle export (transcript + playbook 一起匯出)
- 自動寄出 / 同步到外部系統
- Summary template 客製化（4 sections frozen）
- Tab 之外的 layout 入口（譬如「Summary」按鈕在頁首）
- Markdown editor / 即時編輯
- Status / error_code / version 欄位
- 跨 meeting summary（譬如「過去 5 場會議的決議列表」）
- Cron / 排程觸發

## Risks / Trade-offs

- **Process restart 期間 in-flight task 丟失** → DB 沒寫 row，_inflight dict 也清空；用戶下次 GET 看到 `not_found`，需手動重觸發。Mitigation: 個人 side project 重啟頻率低；且 Vertex 已收費（不能 refund），重觸發成本只是用戶體感
- **Auto-trigger 失敗用戶不知道** → user 切 Summary tab 才看到「沒生成」。Mitigation: 看 backend log + 提供「重新生成」按鈕；可接受
- **Stale 判定 4 表 timestamp** → 加 1 個 SQL；若未來表變多要更新查詢。Mitigation: 集中在 SummaryRepository._build_stale_query() 一處
- **4-heading 驗證 false-positive** → LLM 用「## 重點討論」vs「## 重點討論點」拼字小差異會被判失敗。Mitigation: 驗證用 case-insensitive + trim + 容忍尾綴標點；若仍嚴格，靠 prompt 強制 + 跑 1 次 retry
- **File System Access API 在 macOS Safari 不支援** → blob fallback 啟動，下載到預設 Downloads。Mitigation: 文檔記錄；Sean 用 Chrome 沒事
- **大會議 transcript 超 1MB → token 限制** → Gemini 2.5 Pro 2M context 應付到 ~5 hour 中文會議；side project 不大可能踩到。Mitigation: 真踩到再做 chunk 摘要；YAGNI
- **Summary tab disabled 時用戶不知道為什麼** → hover 才看到提示。Mitigation: hover hint 文案明確「會議結束後可看摘要」；接受
- **In-flight dict 跨 worker 不共享** → 多 worker 部署時 race。Mitigation: 個人 side project 永遠 single-process uvicorn；真要 scale 再改 DB lock

## Migration Plan

1. Alembic migration `0006_create_summary` 建表 + UNIQUE constraint；`alembic upgrade head` 跑過。
2. Backend deploy：新 summarization 模組 + sessions/router.py 的 spawn 一行；舊 meeting end flow 不變（背景 task 是 additive）。
3. Frontend deploy：detail.tsx 包 Tabs，舊 user 看到的 workspace tab 等同舊行為；Summary tab 對 status≠completed meeting 永遠 disabled，舊 meeting 第一次點開會立刻看到「無 summary，可生成」狀態（因為 history meetings 沒 row + 沒 in-flight）。
4. 文件：`docs/agents/summarization.md` 新增。

無 down-migration 需求；rollback 走 `git revert` + `alembic downgrade -1`，DB schema 多一個空表不影響其他功能。
