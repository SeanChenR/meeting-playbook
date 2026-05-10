## Context

Slice 8 上線了 TacticalAdvisor + Get Advice 按鈕 + Vertex Flash streaming，advice cards 在 React reducer 中累積，但只是 ephemeral state — 刷新或結束會議全消失。PRD US #15 / #17 / #19 + Issue #11 早就規劃 button + chatbox 並存 + per-meeting chat history persistence；本 slice 把這條收尾。

當前 advisor 的關鍵設施已就位：
- `TacticalAdvisor` Protocol + `VertexFlashAdvisor` impl (slice 8)
- `prompts.build_user_message` 已組合 playbook + 60s transcript (slice 8)
- WS 4 個 advice frame (`request_advice` / `advice_chunk` / `advice_done` / `advisor_failed`) (slice 8)
- `_run_advice` 在 router 內以 separate AsyncSession 跑 (slice 8)

要新加的本質就兩件事：**(a) 把 advise stream 結果寫進 DB**、**(b) 在 prompt 加進 chat history 段落**。其他都是 UI 跟 wiring。

## Goals / Non-Goals

**Goals:**

- chat history 跨刷新 / 跨會話狀態存活，可在會中 + 會後 detail page 看到完整對話
- 純文字 multi-turn：第二題能理解第一題上下文（advisor 拿得到歷史對話）
- Get Advice button + chatbox 兩條路徑共用同一個 history 表 + 同一個 advise pipeline，避免雙寫法
- Failed / interrupted 對話不污染 DB（refresh 後看到的就是「成功對話」）
- 既有 slice 8 的 `request_advice` WS frame 維持向下相容（不破壞已部署環境）

**Non-Goals:**

- Edit / delete 過去訊息 — read-only history
- Cross-meeting chat history — 只看當場 meeting
- Token budget cap / history truncation — 單場 50 輪幾 KB 內，Vertex Flash 1M context 夠用
- Status / error_code 欄位 — schema 維持 5 欄精簡（per Issue #11）
- 把 slice 8 ephemeral 行為強留 — slice 8 的「streaming 中可看到 partial tokens」UX 維持，但 partial 不寫 DB；refresh 後只看到 done 的訊息
- Voice / image / file attachments

## Decisions

### Decision 1: Schema 5 欄精簡，不加 status / error_code

```sql
CREATE TABLE chat_message (
  id          TEXT PRIMARY KEY,                                       -- cm_xxx
  meeting_id  TEXT NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,                                          -- 'user' | 'advisor'
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (role IN ('user', 'advisor'))
);
CREATE INDEX chat_message_meeting_created_idx ON chat_message (meeting_id, created_at);
```

**Rationale**: Issue #11 acceptance criteria 明確列 5 欄；status / error_code / interrupted 是 grill 階段我自己加的「以防萬一」欄位，YAGNI。配合 Decision 2 的「stream 完整成功才寫」策略，這些欄位本來就用不到。

**Alternatives considered**:
- A: row-per-message + `status: 'streaming'|'done'|'failed'|'interrupted'` + INSERT-on-start UPDATE-on-end → 需 startup hook 處理 stale 'streaming' row、refresh hydrate 時要區分 streaming vs done 顯示 → 複雜度爆增，沒對應價值
- B (採用): row-per-message + INSERT-only-on-success → schema 精簡、無 stale row、refresh 看到的就是已成功對話

### Decision 2: 寫入時機 — advise stream 完整成功才 INSERT user + advisor 兩個 row（單一 transaction）

`_run_advice` 完成 stream 後（`advice_done` 送出之前）開新 AsyncSession，在單一 commit 內寫 user row + advisor row。失敗（timeout / quota / auth / cancelled / unknown）不寫任何 row。

**Rationale**: 失敗對話對 history 沒價值（refresh 後不該看到「我問過但失敗了」的記錄）；不寫 = 重試行為單純（前端 UI state 自己管 in-flight + 失敗顯示，重試 = 重發新的 chat_message frame）。一次 commit 兩 row 保證 user message 不會孤兒（沒 advisor 配對的 user row）。

**Alternatives considered**:
- A: INSERT user immediately + INSERT advisor on done → 失敗會留孤兒 user row → refresh 看到「user 提問但 advisor 沒回」這種詭異狀態
- B (採用): INSERT both on success → 失敗不留痕跡，history 永遠完整

### Decision 3: WS 新 client→server frame `chat_message`，沿用 advice_chunk / advice_done / advisor_failed 回傳

```python
class ChatMessageRequestMessage(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    request_id: str         # client UUID
    content: str            # user input from chatbox; non-empty
    locale: Literal["zh-TW", "en"]
```

舊 `request_advice` frame（slice 8）維持原狀並繼續服務 Get Advice button 路徑（user_question = null，content 由 backend 填預設 prompt 字串再寫 user row）。

**Rationale**: PRD User Stories + Issue #11 acceptance criteria 明確說「new `chat_message` WS message」+「reuses `advice_chunk` / `advice_done`」。沿用 advice_* response frame 表示前端只要新加一個 sender，不需要新加 receiver 邏輯 → 程式碼變動最小。

**Alternatives considered**:
- A: 把 chatbox path 也走 `request_advice` frame（user_question 帶 content）→ 命名不對（"advice" vs "chat"）+ 跟 button path 路徑混淆，未來 Slice 11+ 要加新功能（譬如 chat-only 模式）很難切
- B (採用): 兩個獨立 client frame，共用 response frame

### Decision 4: Get Advice button 路徑也寫 chat_message pair

按下 Get Advice 時，user role content 寫 i18n 預設 prompt 字串（`「請給出戰術建議。」` / `"Please give tactical advice."`）。前端 history 顯示時，user message 看起來就是「請給出戰術建議。」這條訊息。

**Rationale**: 兩條路徑共用同一個 history 表，refresh / 會後檢視時看到完整時間軸（包含按過幾次 button + 打過什麼 chatbox 訊息）；prompt assembly 一致（multi-turn 第二輪能看到第一輪的 button-triggered advice 也是脈絡）。

**Alternatives considered**:
- A: Get Advice button 不寫 DB（保持 slice 8 ephemeral 行為）→ refresh 看不到按過 button、prompt 第二輪 history 段落不一致（chatbox 看得到 button advice 不見，邏輯詭異）
- B (採用): 兩條路徑都寫；user content 用 i18n 預設字串

### Decision 5: Multi-turn prompt 的 chat_history 段落格式

`prompts.py` 新增 `_format_chat_history(messages, locale, me_display_name)`，渲染進 `## 對話紀錄` heading 段落，接在 `## 最近 60 秒對話` 後面、最終 question 行之前：

```markdown
## 對話紀錄

Sean: 對方剛說 budget 的問題，怎麼回？
Advisor: - **直接 push close**...
        - 強調 ROI...

Sean: 如果他繼續砍價呢？
Advisor: - **不要先讓步**...
```

`me_display_name` 用作 user role label（與 60s transcript 段落一致）；`Advisor` 是固定字串（不是 counterparty_display_name）。空 history 時整個段落不渲染（不印空 heading）。

**Rationale**: 跟 60s dialog 段落格式一致，model 容易區分「過去對話」vs「當下 transcript」。`Advisor` 固定字串避免跟 counterparty 混淆。

### Decision 6: Chat history hydrate 走獨立 GET API，React Query 抓

新 endpoint `GET /api/meetings/{id}/chat_messages` → JSON array of ChatMessage，按 created_at ASC。`useMeetingSession(meetingId)` hook 內部用 React Query 抓 → 載入完 dispatch `HISTORY_LOADED` action 注入 reducer initial state。Detail page mount 時觸發一次。

**Rationale**: 對齊現有 `transcripts-api.ts` / `meetings-api.ts` 模式（每張表一個 API module + queryOptions）。把 hydrate 放 hook 內部讓 detail page 不用知道；React Query cache key 為 `["chat_messages", meetingId]`，advise stream 完成後 invalidate 即可重抓最新。

**Alternatives considered**:
- A: WS 連線時 server 主動推一個 `chat_history_snapshot` frame → 把 hydrate 跟 stream 耦合，且需要新 server frame
- B (採用): GET API + React Query；獨立、可緩存、可手動 refetch

### Decision 7: Cancel-previous policy — chatbox path 觸發時 cancel in-flight advice task

新 `chat_message` frame 進來時，router 的 `_client_listener` 跟 slice 8 的 `request_advice` 分支一樣：if `advice_task and not advice_task.done()` 先 cancel + await（同邏輯）。前端 chatbox Send 期間 disabled 避免雙送。

**Rationale**: 沿用 slice 8 既定行為；user 送新訊息時對舊回答失去興趣是合理假設；不寫 DB 表示被 cancel 的對話自然不留痕跡。

### Decision 8: AdvisorPane 三段式佈局（per Sean 拍板）

```
┌─ Tactical advisor ────────┐
│ (history list 上半)        │
│   user msg / advisor msg  │
│   ...auto-scroll-to-bottom │
│                            │
│ [ Get Advice ]  ← 中間     │
│ ───────────────────────── │
│ [ textarea ]   [ Send ]    │
└────────────────────────────┘
```

當 `phase !== "in_progress"` 時：history 仍顯示，button + textarea + Send 全部隱藏（advisor 需要 live transcript 60s 段才有 context）。

當 `phase === "in_progress"` 時：button + textarea + Send 顯示；button + Send 在有 in-flight advice 時都 disabled。

textarea: Cmd+Enter 送出；Send empty 時 disabled；Cmd+Enter shortcut 提示放在 textarea 下方小字。

## Implementation Contract

### Behavior contract

1. **Chat history persistence**: 每次 advise stream 在 `advice_done` 送出之後（且僅在 done 時），backend INSERT 一對 (user, advisor) chat_message row 到 DB（單一 transaction）。失敗 / cancelled / interrupted 時不寫任何 row。
2. **History hydrate**: Detail page mount 時前端 GET `/api/meetings/{id}/chat_messages`，把回傳的訊息陣列按 created_at ASC 灌進 advisor reducer state；UI 顯示時 user / advisor 訊息有不同樣式（user 靠右 / advisor 靠左）。
3. **Chatbox send**: 用戶在 textarea 輸入 + 按 Send（或 Cmd+Enter）→ 前端送 WS frame `chat_message {request_id, content, locale}` → backend 收到 → cancel in-flight advice → spawn `_run_advice(user_question=content, chat_history=<from DB>)` → stream `advice_chunk` × N → `advice_done` → INSERT pair → invalidate React Query cache → refetch hydrate。
4. **Get Advice button**: 用戶按 button → 前端送 WS frame `request_advice {request_id, locale}` (沒有 user_question) → backend 用 i18n 預設字串作為 user content → 同 chatbox 路徑後續流程。
5. **Multi-turn context**: 第二輪以後，prompt 的 user_message 段落新增 `## 對話紀錄` heading，列出本場 meeting 之前所有 user / advisor 對話，按 created_at ASC。
6. **Refresh behavior**: 使用者刷新瀏覽器 → 重 mount detail page → React Query hydrate → 看到所有已成功的對話訊息；in-flight 中的對話（被打斷）不出現在 history。

### Data shapes

ChatMessage TypeScript:
```typescript
type ChatMessage = {
  id: string;                      // cm_xxx
  meeting_id: string;
  role: "user" | "advisor";
  content: string;
  created_at: string;              // ISO8601
};
```

GET response: `ChatMessage[]` ordered by `created_at` ASC (oldest first).

WS client→server `chat_message`:
```json
{ "type": "chat_message", "request_id": "<uuid>", "content": "<text>", "locale": "zh-TW" | "en" }
```

WS server→client (沿用 slice 8): `advice_chunk` / `advice_done` / `advisor_failed` 三個 frame 不變。

### Failure modes

- **Stream timeout / quota / auth / unknown**: 沿用 slice 8 — 送 `advisor_failed` frame，**不寫 DB**；前端 UI 在 in-flight advice card 顯示錯誤 + retry button；retry 行為 = 重發 `chat_message` frame（chatbox path）或 `request_advice` frame（button path）
- **Cancelled by new chat_message**: backend 靜默 cancel，不送 frame，不寫 DB；前端把上一個 in-flight card 標記為「已被新訊息打斷」（純 UI state，不持久化）
- **WS disconnect mid-stream**: 沿用 slice 8 finalize block 的 cancel 邏輯；不寫 DB；refresh 後該對話不在 history
- **DB INSERT 失敗**: 已經把 `advice_done` 送出去了，前端會看到 done 但 history refetch 會發現訊息不在 → 預期罕見，記 warning log；前端容忍 race（done 後等 refetch 才確認 persisted）
- **Empty content**: client→server frame validation reject (`content` 為空字串時 Pydantic raise ValidationError → 既有 `session.unknown_message` error frame）

### Acceptance criteria

- 後端 `pytest packages/backend` 全綠（含新 chat repo / router / migration / advisor multi-turn 測試）
- 前端 `bun test packages/web` 無新失敗（slice 8 既有 8 個 baseline 失敗可保留）
- locale parity guard (`packages/web/src/locales/locales.test.ts`) 過
- Manual smoke test：開 meeting → in_progress → 按 Get Advice → 看到 user message "請給出戰術建議。" + advisor 回覆 → chatbox 輸入「他剛說的怎麼回」→ Send → 看到第二對訊息，且 advisor 回覆能 reference 上一輪內容 → 刷新瀏覽器 → 兩對訊息都還在 → end meeting → history 仍可見

### Scope boundaries (in / out)

**In scope**:
- chat_message 表 + Alembic migration
- ChatMessageRepository (list_for_meeting + insert_pair_after_advice)
- 新 WS frame `chat_message`
- TacticalAdvisor + prompts.py 加 chat_history 參數
- Router `_run_advice` 改寫支援 INSERT pair on success + 兩條 client path
- AdvisorPane 重做（history list + button + chatbox）
- GET API + React Query hydrate
- i18n keys
- 既有 advisor / advisor-pane / use-meeting-session / detail / session-ws 測試覆寫

**Out of scope**:
- 新 capability（不新增 chat capability，全部歸 tactical-advisor）
- Edit / delete past messages
- Cross-meeting chat history queries
- Chat history 匯出 / 列印
- Slice 8 reducer 的 `requests: AdviceRequest[]` 結構保留 — 直接被 `messages: ChatMessage[]` 取代
- AdvisorPane 樣式大改（沿用 slice 8 的 Card / Button / shadcn 樣式 ; UI overhaul 待 slice-08-ui-overhaul）
- ChatMessageRepository 提供任何 update / delete API
- Slice 8 button 路徑的舊 ephemeral cards 行為保留 — 從本 slice 起，所有 advice 都走「INSERT pair on done」路徑
- Voice / image / file attachments
- Per-message 評分 / reactions

## Risks / Trade-offs

- **失敗對話完全不留痕跡** → 沒記錄使用者「按了多少次但失敗」這種 ops 訊號；但 backend log 已有 `logger.exception` 記錄完整 traceback，需要 ops 分析時去 log 撈
- **DB INSERT 在 advice_done 之後** → 理論上 `advice_done` frame 已到前端但 INSERT 失敗 → refresh 後看不到該對話。Mitigation: backend log warning + 前端 done 後等 React Query refetch 才當 persisted
- **Cancel-previous 用 send-side disable** → 用戶看到 disabled 才知道 in-flight，不夠明顯。Mitigation: in-flight card 上方的 thinking indicator + Send 按鈕 disabled 已是 visual cue
- **Get Advice button user content 是 i18n 字串** → 切換語言後 history 會混合 zh-TW 跟 en 預設 prompt 字面 → 罕見場景；個人 side project 使用者只有 Sean，不會切；切的話也只是看到「Please give tactical advice.」跟「請給出戰術建議。」混雜，不影響功能
- **Multi-turn context 沒上限** → 100 輪以後 prompt 變超長 → 罕見場景；個人會議不會聊 100 輪。真到那天 Slice 11+ 加 truncation
- **Slice 8 reducer state shape 改變 (`requests` → `messages`)** → 若使用者瀏覽器有舊 cache 跑舊版本 reducer 會 crash。Mitigation: dev-only side project，使用者就是 Sean，刷新一次就好；無 graceful migration 必要

## Migration Plan

1. Alembic migration `0005_create_chat_message`：建表 + index + FK CASCADE；`alembic upgrade head` 跑過。
2. Backend deploy 新 `_run_advice` (寫入策略改變)；舊 ephemeral 行為消失；既有 `request_advice` frame 繼續 work（多寫一個 chat_message pair）。
3. Frontend deploy 新 AdvisorPane：舊 reducer state shape 不再有效，使用者刷新瀏覽器一次後正常。
4. 文件：`docs/agents/advisor.md` 加 chat_history + persistence 段。

無 down-migration 需求（個人 side project，rollback 走 `git revert` 即可，DB schema 留下不痛）。
