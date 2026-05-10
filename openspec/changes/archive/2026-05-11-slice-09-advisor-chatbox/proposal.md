- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/11
- PRD User Stories：https://github.com/SeanChenR/meeting-playbook/issues/1 (US #15, #17, #19)

## Why

Slice 8 已上 Get Advice button + 即時 Vertex Flash streaming。但 advice cards 純前端 state，刷新或結束會議就消失，且只能「按一鍵取得無 context 建議」。PRD US #17 + US #19 + Issue #11 早已規劃 chatbox follow-up + per-meeting chat history persistence — 本 slice 把這個收尾，advisor 從 single-shot 升級為 multi-turn conversation，並且持久化到 DB（refresh 後可看到歷史、會後也能回顧對話）。

## What Changes

- 新表 `chat_message`（5 欄：id, meeting_id FK CASCADE, role enum `user`|`advisor`, content text, created_at TIMESTAMPTZ）+ Alembic migration + 複合 index `(meeting_id, created_at)`
- 新 `ChatMessageRepository`（list_for_meeting + insert_pair_after_advice 兩個方法）
- WS 新 client→server frame `chat_message {request_id, content}`；advisor stream 沿用既有 `advice_chunk` / `advice_done` / `advisor_failed`
- `TacticalAdvisor.advise()` 加 `chat_history: list[ChatMessage]` 參數；`prompts.py` 新增 `## 對話紀錄` 段落（接在 60s transcript 後、最終 question 前）
- Router `_run_advice` 寫入策略：advise stream **完整成功**才 INSERT (user, advisor) 兩個 row 在單一 transaction；失敗或中斷不寫 DB（前端純 UI state 提示重試）
- Get Advice button 路徑也走相同寫入：user role content = i18n 預設 prompt `「請給出戰術建議。」` / `"Please give tactical advice."`，這樣 history 完整、prompt assembly 一致
- 新 GET API `/api/meetings/{id}/chat_messages` → 按 created_at ASC 列出 history
- AdvisorPane 重做：上半 history 列表（user / advisor 訊息分開樣式）+ 中間 Get Advice button + 下半 chatbox 輸入框 + Send；輸入框 textarea，Cmd+Enter 送出；Send empty 時 disabled
- `useMeetingSession` 內部用 React Query 抓 chat_messages → dispatch `HISTORY_LOADED` 注入 reducer initial state；advisor reducer 改為 `messages: ChatMessage[]` 取代原 `requests: AdviceRequest[]`
- Cancel-previous policy: 新 chat_message 進來時 cancel 上一個 in-flight advice task（沿用 slice 8 邏輯）；前端 Send 期間 disabled 避免 race
- i18n 新 keys：`meetings.advisor.chatPlaceholder`, `meetings.advisor.send`, `meetings.advisor.defaultPromptText`, `meetings.advisor.userLabel`, `meetings.advisor.advisorLabel`, `meetings.advisor.cmdEnterHint`

## Non-Goals

- Edit / delete 過去的 chat message — read-only history
- Cross-meeting chat history — 只看當場 meeting
- Token budget cap / history truncation — 單場 50 輪幾 KB，Vertex Flash 1M context 沒問題；真會議過長再說
- Voice input / voice output — 純文字
- Image / file attachments
- Streaming 中 partial state 寫進 DB — 只在 stream 成功後寫；中斷不留 DB 痕跡
- Status / error_code 欄位 — schema 維持 5 欄精簡
- Markdown editor for chatbox input — 純 textarea；advisor 回覆才 render markdown
- Per-message reactions / 評分 — 將來 Slice 11+ 才考慮（訓練資料用途）
- Chat history 匯出成檔案 — 從 DB 直接撈 SQL 即可；UI 不曝光
- Slice 8 button-only 路徑保留性 — 本 slice 取代 slice 8 AdvisorPane 整個元件，但 backend `request_advice` WS frame 維持向下相容（chatbox 用新 frame，button 仍可用舊 frame）

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `tactical-advisor`: chatbox 路徑 + chat history persistence + multi-turn context assembly；新增 ChatMessageRepository、`chat_message` 表、`chat_history` 參數；新增 GET API for history hydrate
- `meeting-session`: 新 client→server frame `chat_message`；router 新分支 spawn advice task 帶 chat_history；finalize 流程的 cancel-previous 行為延伸到 chatbox 路徑
- `meeting-detail-layout`: AdvisorPane 從 button-only cards 重做為 history list + button + chatbox 三段式佈局；columns + stack 兩種版型都套用

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0005_create_chat_message.py`（migration）
  - `packages/backend/meeting_playbook/chat/__init__.py`
  - `packages/backend/meeting_playbook/chat/models.py`（ChatMessage SQLAlchemy ORM）
  - `packages/backend/meeting_playbook/chat/repository.py`（ChatMessageRepository — list_for_meeting + insert_pair_after_advice）
  - `packages/backend/meeting_playbook/chat/router.py`（GET /api/meetings/{id}/chat_messages endpoint）
  - `packages/backend/tests/chat/__init__.py`
  - `packages/backend/tests/chat/test_repository.py`
  - `packages/backend/tests/chat/test_router.py`
  - `packages/backend/tests/test_alembic_chat_message.py`（migration round-trip + FK CASCADE）
- 後端修改：
  - `packages/backend/meeting_playbook/advisor/base.py`（TacticalAdvisor Protocol 加 chat_history 參數）
  - `packages/backend/meeting_playbook/advisor/vertex_advisor.py`（傳 chat_history 進 prompts.build_user_message）
  - `packages/backend/meeting_playbook/advisor/prompts.py`（新增 `_format_chat_history` + 加進 build_user_message）
  - `packages/backend/meeting_playbook/sessions/messages.py`（新 ChatMessageRequestMessage Pydantic + 加進 ClientMessage union）
  - `packages/backend/meeting_playbook/sessions/router.py`（_client_listener 新分支 ChatMessageRequestMessage → spawn _run_advice 帶 user_question + chat_history；_run_advice 完成時 INSERT chat_message pair；reuse advice_chunk/done/failed frames）
  - `packages/backend/meeting_playbook/server.py`（mount chat router）
  - `packages/backend/tests/advisor/test_prompts.py`（chat_history 段落渲染 + multi-turn fixture）
  - `packages/backend/tests/advisor/test_vertex_advisor.py`（chat_history 傳遞）
  - `packages/backend/tests/sessions/test_messages.py`（chat_message 序列化）
  - `packages/backend/tests/sessions/test_router_advice.py`（chatbox 路徑 + INSERT pair on done + cancel-previous 兩條路徑互動）
- 前端新檔：
  - `packages/web/src/lib/chat-api.ts`（GET /api/meetings/{id}/chat_messages + ChatMessage TS type + queryOptions）
  - `packages/web/src/lib/chat-api.test.ts`
  - `packages/web/src/components/chat-input.tsx`（textarea + Send button + Cmd+Enter shortcut）
  - `packages/web/src/components/chat-input.test.tsx`
  - `packages/web/src/components/chat-message-list.tsx`（user / advisor 分開樣式 + auto-scroll）
  - `packages/web/src/components/chat-message-list.test.tsx`
- 前端修改：
  - `packages/web/src/components/advisor-pane.tsx`（重做 — 整合 chat-message-list + Get Advice button + chat-input；hydrate 後從 React Query 灌 history）
  - `packages/web/src/components/advisor-pane.test.tsx`（覆寫 — 新 history rendering + chatbox interaction tests）
  - `packages/web/src/hooks/use-meeting-session.ts`（reducer messages: ChatMessage[]；新 actions HISTORY_LOADED + USER_MESSAGE_SENT + ASSISTANT_MESSAGE_DONE / FAILED；新 callback sendChatMessage(content)）
  - `packages/web/src/hooks/use-meeting-session.test.tsx`（新 chatbox lifecycle 測試）
  - `packages/web/src/lib/session-ws.ts`（新 ChatMessageRequestMessage TS type + ClientMessage union 擴充）
  - `packages/web/src/lib/session-ws.test.ts`（新 frame 序列化測試）
  - `packages/web/src/routes/meetings/detail.tsx`（hydrate chat history via React Query；session.start() 之後再注入）
  - `packages/web/src/routes/meetings/detail.test.tsx`（hydrate flow + chatbox visible only when in_progress）
  - `packages/web/src/locales/zh-TW.json`（新 advisor chatbox keys）
  - `packages/web/src/locales/en.json`（同上）
- 文件：
  - `docs/agents/advisor.md`（更新 multi-turn context + persistence + chatbox UI 段落）
