- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/10

## Why

Slice 6 + 7 把「會中即時逐字稿」整條 pipe 立起來；Slice 5 把「會前 playbook」自動生成串通。兩端齊備了，**會中真正的價值 — 戰術建議 (tactical advisor)** 才能落地：使用者開會邊聽邊看 transcript，按下 `Get Advice` 一鍵拿到「對方剛說的這段，建議怎麼回」3-5 條 markdown bullet。Vertex Gemini Flash + last-60s transcript + full playbook = ADR-0017 / ADR-0018 既定路徑。本 slice 是 in-meeting LLM 體驗的開場，後續 Slice 9 (chatbox follow-up) + Slice 10 (post-meeting summary) 都站在這上面。

## What Changes

- 後端新增 `TacticalAdvisor` deep module（Vertex Flash streaming wrapper）+ context assembly（last 60s transcript via `started_at >= now() - 60s` SQL + non-empty playbook 欄位）
- WS 新 4 個 frame：`request_advice` (client→) / `advice_chunk` `advice_done` `advisor_failed` (→client)；`request_advice` 已預留 `user_question?` + `locale` 兩個欄位（Slice 9 chatbox 升級用）
- AdvisorPane 從 placeholder 換成真元件：`Get Advice` 按鈕 + chat-style 累積 cards；每張 card stream 完整 markdown，最新在下，自動 scroll-to-bottom；in-flight 期間 button disabled
- PlaybookPane 在 in_progress 狀態維持可編輯（行為已存在，本 slice 確認 + 加 ws session 並行測試）
- Detail 頁 columns mode 中欄寬度不變（30/40/30），advisor 換成真元件
- Concurrency: advisor task 開新 AsyncSession（透過 `get_session_factory_dependency`），不跟 capture/transcribe 共享 session lock；Vertex Flash 平均 < 5s，硬上限 15s timeout
- i18n keys：`meetings.advisor.{getAdviceButton, thinking, retry, emptyState}` + `errors.advisor.{timeout, quota, auth, unknown}`
- 新增 dependency injection：`get_session_factory_dependency`（async_sessionmaker）+ `get_tactical_advisor_dependency`（單例）
- TacticalAdvisor 不持 session — caller 把 chunks + playbook 餵進來，職責純粹（為 Slice 9 chatbox follow-up 鋪路）

## Non-Goals

- Chatbox follow-up — Slice 9 (Issue #11)；本 slice WS contract 預留 `user_question` field 但 UI 不曝光
- Auto-trigger advice (每 30s 自動跳出) — ADR-0017 explicit reject；revisit 等真有需求
- Advice history 跨 reload 持久化 — 純 client state，meeting reload 後 cards 會掉；Slice 9 chatbox 進來才考慮 schema
- 自製 prompt caching — Gemini SDK 自動處理 system_instruction caching；不另外做
- Streaming 取消 / 中斷 — Slice 8 button-only，disable button 期間連點不可能；end_meeting / disconnect 直接 cancel task
- Multiple in-flight requests — Slice 8 一次一個；Slice 9 chatbox 升級時再決定 cancel-previous policy
- Advice 寫進 DB — 純 ephemeral；Slice 10 summary 用的是 transcript + playbook 不是 advisor history
- Per-meeting advisor on/off toggle — 全 meeting 一律可用
- 多語自動偵測 (transcript 偵測) — 跟 user `i18n.language`，明確可預期

## Capabilities

### New Capabilities

- `tactical-advisor`: 會中 LLM 戰術建議的完整契約 — TacticalAdvisor module（Vertex Flash streaming wrapper）+ context assembly 規則（last 60s + playbook non-empty fields）+ 4 個 WS frame + AdvisorPane UI（chat-style cards + retry）+ 並發處理（新 AsyncSession + 不共享 session lock）+ error code mapping (timeout / quota / auth / unknown)

### Modified Capabilities

- `meeting-session`: WS contract 加 4 個 frame；`_client_listener` 加 `request_advice` 分支 spawn advice task；finalize 流程 cancel in-flight advice task
- `meeting-detail-layout`: Advisor pane 從 placeholder 換成真元件 `<AdvisorPane meetingId={id} session={session} />`；columns / stack 兩種版型都套用

## Impact

- 後端新檔：
  - `packages/backend/meeting_playbook/advisor/__init__.py`
  - `packages/backend/meeting_playbook/advisor/base.py`（TacticalAdvisor Protocol + AdviceContext dataclass）
  - `packages/backend/meeting_playbook/advisor/vertex_advisor.py`（Vertex Flash streaming impl）
  - `packages/backend/meeting_playbook/advisor/prompts.py`（system_instruction + user_message builder + LOCALE_INSTRUCTION dict）
  - `packages/backend/meeting_playbook/advisor/dependencies.py`（FastAPI deps：get_tactical_advisor_dependency 單例 + get_session_factory_dependency）
  - `packages/backend/tests/advisor/__init__.py`
  - `packages/backend/tests/advisor/test_prompts.py`（context assembly + non-empty filtering + locale switch）
  - `packages/backend/tests/advisor/test_vertex_advisor.py`（mock Vertex client + assert streaming yield + timeout 路徑）
  - `packages/backend/tests/sessions/test_router_advice.py`（WS 整合測試 — request_advice → advice_chunk × N → advice_done；timeout → advisor_failed；end_meeting cancel in-flight）
- 後端修改：
  - `packages/backend/meeting_playbook/sessions/messages.py`（4 個新 Pydantic class + 加入 ServerMessage / ClientMessage discriminated union）
  - `packages/backend/meeting_playbook/sessions/router.py`（_client_listener 加 RequestAdviceMessage 分支；spawn _run_advice task；finalize 取消 in-flight；接 get_session_factory + tactical_advisor dependency）
  - `packages/backend/meeting_playbook/sessions/repository.py`（新增 `list_chunks_last_60s(meeting_id) -> list[TranscriptChunk]`）
  - `packages/backend/meeting_playbook/playbooks/repository.py`（確認 `get_for_meeting` 已存在，否則新增）
  - `packages/backend/meeting_playbook/meetings/dependencies.py`（新增 `get_session_factory_dependency` returning async_sessionmaker）
  - `packages/backend/meeting_playbook/config.py`（新增 `vertex_flash_model_id` 設定，default `gemini-2.0-flash-001` 或同等 Flash 變體）
  - `packages/backend/tests/sessions/test_messages.py`（4 個新 frame 序列化 / discriminated union 測試）
  - `packages/backend/tests/sessions/test_repository.py`（`list_chunks_last_60s` window 邊界測試）
- Auth gateway：不動（WS upgrade + identity headers 已具備）
- 前端新檔：
  - `packages/web/src/components/advisor-pane.tsx`（chat-style cards + Get Advice button + streaming render + retry）
  - `packages/web/src/components/advisor-pane.test.tsx`
  - `packages/web/src/lib/advisor-ws.ts`（薄 wrapper 在現有 useMeetingSession 之上，暴露 advice request / streaming token state）— 或直接擴 useMeetingSession，apply 階段拍板
- 前端修改：
  - `packages/web/src/hooks/use-meeting-session.ts`（reducer 加 ADVICE_* actions：started / token / done / failed；state 加 `advisor: { requests: AdviceRequest[] }`）
  - `packages/web/src/hooks/use-meeting-session.test.tsx`（新 advice 流程測試）
  - `packages/web/src/lib/session-ws.ts`（4 個新 message type 加入 SessionMessage discriminated union；ClientMessage 加 RequestAdviceMessage）
  - `packages/web/src/lib/session-ws.test.ts`（parse 4 個新 frame）
  - `packages/web/src/routes/meetings/detail.tsx`（advisor pane placeholder 換成 `<AdvisorPane>`，傳 session 進去）
  - `packages/web/src/routes/meetings/detail.test.tsx`（assert advisor pane 真實渲染 + Get Advice button 存在）
  - `packages/web/src/locales/zh-TW.json` + `en.json` + `locales.test.ts`（meetings.advisor.* + errors.advisor.*）
- 前端依賴：無新增（react-markdown 已具備、Card / Button 既有 shadcn）
- 文件：
  - `docs/agents/advisor.md`（新檔 — TacticalAdvisor 架構、context assembly 規則、prompt 結構、failure modes、Slice 9 升級點）
- 環境：
  - `.env.example` 新增 `VERTEX_FLASH_MODEL_ID`（optional，default `gemini-2.0-flash-001`）
- 不動：所有 Calendar / playbook generation / ASR / sessions capture / scheduled_at / detail layout / calendar view 模組
