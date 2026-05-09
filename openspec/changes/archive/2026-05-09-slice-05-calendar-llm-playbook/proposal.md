- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/7
- Agent Brief：https://github.com/SeanChenR/meeting-playbook/issues/7#issuecomment-4386426445

## Why

Slice 4 已交付手動 playbook 編輯器，使用者必須從零打字填 6 個欄位。PRD 的核心價值是「會前自動準備」：使用者授權 Google Calendar 讀取，從即將到來的 24 小時 events 一鍵匯入，後端用 Gemini 2.5 Pro 從 event metadata（title / attendees / time / description）生成 playbook 草稿，使用者落到編輯器看到已填好的 6 個結構化欄位。這是 LLM 第一次在本應用裡被呼叫，也是 `calendar_event_id`（slice-3 預留）第一次被填值。

## What Changes

- 在 settings 新增 **「連結 Google Calendar」流程**（與既有 login OAuth 分離；Calendar scope 較廣），透過 Better Auth 的 `linkSocial` 或新開的 `/api/auth/google/calendar-link` 端點，授予 `https://www.googleapis.com/auth/calendar.events.readonly`；token 存進 Better Auth account row（或新建 `calendar_token` 表，由 design 拍板）
- 後端新增 **`CalendarClient`**（Python module）— 包 Google Calendar API：`get_upcoming_events(user_id, hours)` 回傳 events，含 pagination 與空清單；token 過期時用 refresh token 自動續期，refresh 失敗回 `calendar.token_expired` error_code
- 後端新增 **`PlaybookGenerator`**（deep module）— 使用 `google-genai` SDK 呼叫 Vertex AI 的 Gemini 2.5 Pro，從 event metadata 產出 7 欄位 playbook（free_form_markdown + 6 結構化）；prompt 工程確保 sparse event（只有 title）也能產出非空草稿（fallback 用「best practices for X 類會議」prompt）
- 兩個 FastAPI endpoints：
  - `GET /api/calendar/upcoming?hours=24` — 已連結 Calendar 的 user 回 events 陣列；未連結回 `calendar.not_connected` error_code
  - `POST /api/meetings/from-calendar` body `{event_id}` — 透過 `MeetingRepository.create` 建 meeting（title 取自 event、`calendar_event_id` 填入）+ 透過 `PlaybookRepository.upsert_for_meeting` 寫入 LLM 產出的草稿 + 回傳 `{meeting_id}`
- React 新增 `/calendar` route（"Upcoming events"）：列出 events、每列「匯入並生成」按鈕；按下後 disable + spinner，成功後 redirect 至 `/meetings/:id`（playbook 已可見）
- 從 `/meetings`（list page）加一個「從 Calendar 匯入」入口連到 `/calendar`
- TanStack Query hooks：`upcomingEventsQueryOptions(hours)` + `useImportFromCalendarMutation`，匯入成功後 invalidate `["meetings"]`
- 失敗模式統一走 error envelope：`calendar.not_connected` / `calendar.token_expired` / `calendar.network_error` / `playbook.generation_timeout` / `playbook.generation_failed`，前端對應 i18n 字串
- i18n keys 雙語齊備（`calendar.*`、`errors.calendar.*`、`errors.playbook.*`）

## Non-Goals

- Google 以外的 Calendar provider（Outlook / iCal）
- 雙向同步（寫回 Calendar）— 唯讀
- Webhook / push notifications — 使用者進到頁面才拉
- 重複會議系列去重或合併
- 從 Gmail / Notion / Linear 等其他來源拉內容
- 匯入頁面行內編輯草稿（一律 redirect 到既有編輯器）
- 跨 request 的 Calendar event 快取（每次拉新的）
- 自動匯入排程（cron 或背景生成）— 使用者點按鈕才生
- 客製 prompt template（v1 固定 prompt；客製化留待後續）

## Capabilities

### New Capabilities

- `calendar-integration`: Calendar OAuth scope grant 流程、token 儲存與續期、`CalendarClient` 模組、`GET /api/calendar/upcoming` 與 `POST /api/meetings/from-calendar` 兩條 endpoint 的契約、Calendar 失敗模式（未連結 / token 過期 / 網路錯誤）的 error_code 對應
- `playbook-generation`: `PlaybookGenerator` deep module、Vertex AI Gemini 2.5 Pro 呼叫契約、event metadata → 7 欄位 playbook 的 prompt 工程、sparse-event fallback、生成失敗模式（timeout / 上游錯誤）的 error_code 對應

### Modified Capabilities

(無) — meeting-management 與 playbook-management 既有契約不變；新 endpoint 透過既有 repository 寫入。

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0003_create_calendar_token.py`（如 design 決定獨立表；或刪除此項）
  - `packages/backend/meeting_playbook/calendar/__init__.py`
  - `packages/backend/meeting_playbook/calendar/client.py`
  - `packages/backend/meeting_playbook/calendar/router.py`
  - `packages/backend/meeting_playbook/calendar/schemas.py`
  - `packages/backend/meeting_playbook/calendar/token_store.py`
  - `packages/backend/meeting_playbook/playbook_generation/__init__.py`
  - `packages/backend/meeting_playbook/playbook_generation/generator.py`
  - `packages/backend/meeting_playbook/playbook_generation/prompts.py`
  - `packages/backend/tests/calendar/test_client.py`
  - `packages/backend/tests/calendar/test_endpoints.py`
  - `packages/backend/tests/playbook_generation/test_generator.py`
  - `packages/backend/tests/playbook_generation/fixtures/`（rich / sparse / long / 中 / 英 / 中英混 6 份 event JSON）
- 後端新依賴：`google-genai`（Vertex AI SDK）、`google-api-python-client` + `google-auth` 系列（Calendar API）
- 後端修改：
  - `packages/backend/pyproject.toml`（新增依賴）
  - `packages/backend/meeting_playbook/server.py`（mount calendar router）
  - `packages/backend/tests/conftest.py`（如新增 `calendar_token` 表，補 TRUNCATE）
- Auth 修改：
  - `packages/auth/src/server.ts` 或 `packages/auth/src/auth.ts`（Better Auth 設定，加 Calendar scope link 流程）
- 前端新檔：
  - `packages/web/src/lib/calendar-api.ts`
  - `packages/web/src/lib/calendar-api.queries.test.ts`
  - `packages/web/src/lib/calendar-api.mutations.test.tsx`
  - `packages/web/src/routes/calendar/upcoming.tsx`
  - `packages/web/src/routes/calendar/upcoming.test.tsx`
  - `packages/web/src/routes/calendar/connect.tsx`（連結 Calendar 入口，或併入 settings 頁）
- 前端修改：
  - `packages/web/src/route-tree.tsx`（新增 `/calendar` route）
  - `packages/web/src/routes/meetings/list.tsx`（加「從 Calendar 匯入」入口）
  - `packages/web/src/locales/zh-TW.json`
  - `packages/web/src/locales/en.json`
  - `packages/web/src/locales/locales.test.ts`
- 環境：
  - `.env.example` 新增 `VERTEX_AI_PROJECT` / `VERTEX_AI_LOCATION`（或沿用既有）、Google Calendar OAuth client id 已沿用 login OAuth 設定
- 不動：`openspec/specs/{auth-gateway-contract,meeting-management,playbook-management}/`、ASR / audio 任何模組（slice-06+ 才碰）

## Post-implementation revisions (ingested 2026-05-09)

Smoke testing the import flow surfaced two correctness gaps. They are folded into this slice:

### Display-name derivation gap

The first ingested `import-from-calendar` rows showed `me_display_name = "Me"` (hardcoded fallback) and `counterparty_display_name = event.organizer`. Both are wrong:

- The signed-in user's real name is already in the Better Auth session — the gateway must propagate it so the FastAPI handler can populate `me_display_name`.
- The Calendar event's `organizer` is whoever created the event, which is often the signed-in user themself (when they self-organize) or a course-calendar bot (when the event comes from a subscribed calendar). The "counterparty" should be the **first attendee whose email is NOT the signed-in user's email**, with a fallback chain when no other attendee exists.

### Calendar requires a Google identity link

The connect flow uses Better Auth's `linkSocialAccount` against the `google` provider. This works for any logged-in user — including those who originally signed in via email + password — but the side effect is that their account becomes Google-linked after granting Calendar scope. Users without a Google account cannot use Calendar at all in this slice. This boundary belongs in `docs/agents/calendar.md` so future agents do not reinvent it.

### Out of scope (deferred)

The free-form Markdown surface in the playbook editor (Slice 4 deliverable) renders raw markdown source — no preview, no WYSIWYG. This is unrelated to Calendar / LLM generation. **Do not address it in this slice.** Open a separate change after slice-05 archive.

## Post-implementation revisions ingested 2026-05-09 (round 2: viewer perspective)

Smoke testing the import flow with a real Calendar event ("實戰營 Live Session 2", a class-calendar event Sean did not organize) revealed that the LLM generates from an indeterminate point of view. Symptoms:

- The playbook reads as if Sean were hosting / driving the meeting, even though he is just an attendee on a course calendar.
- `objective`, `talking_points`, and `red_lines` come out worded for the wrong actor.
- The prompt has no signal telling the model who the viewer is, only what the event metadata says.

Root cause: `PlaybookGenerator.generate(event)` takes only the event. It has no awareness of the signed-in user's identity or their role in the meeting. The previous ingest round fixed `me_display_name` and `counterparty_display_name` at the meeting row layer, but the LLM call still flies blind.

This round folds the viewer perspective into the slice:

1. Add `organizer_email` to `CalendarEvent` so we can compare the viewer's email to the organizer's email separately from the human-readable display name.
2. Change the generator signature to `generate(event, viewer_email, viewer_name) -> PlaybookDraft`. Old call sites (router) are updated; tests pass viewer args explicitly.
3. The router feeds `X-User-Email` and `X-User-Name` (already set by the gateway in the previous ingest) through to the generator.
4. Prompts (`build_primary_prompt`, `build_fallback_prompt`) take the viewer args and emit a leading paragraph that names the viewer, classifies their role (`organizer` / `attendee` / `external`), names the other parties, and instructs the model to write the playbook from the viewer's point of view.

Role-classification rule:
- `organizer` — viewer's email matches the event organizer's email (case-insensitive, trimmed)
- `attendee` — viewer's email appears in `attendees` but is not the organizer
- `external` — viewer's email is neither the organizer nor an attendee (this is the "I'm previewing someone else's event from a calendar I subscribe to" case — like the Sean / class-calendar example above)

The role label is what the prompt uses; the wire-format meeting row continues to use the previous ingest round's `pick_counterparty` algorithm for `counterparty_display_name`.
