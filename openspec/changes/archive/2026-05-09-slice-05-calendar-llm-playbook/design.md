## Context

Slice 4 把 manual playbook editor 立起來（`PlaybookRepository.upsert_for_meeting` 是 7 欄位寫入的唯一通道）。本 slice 是 LLM 第一次接入應用、Calendar 第一次被讀取，也是「會前自動準備」價值兌現的關鍵步。

依 ADR-0014 / ADR-0015 / ADR-0021 / ADR-0023：LLM 走 Vertex AI 上的 Gemini 2.5 Pro（`google-genai` SDK，**不**用 Anthropic / OpenAI 直連）；Bun gateway 仍是唯一 ingress；Better Auth 管所有 OAuth 帳號表，Alembic 管應用表。Slice 1 的 Google login OAuth 已綁 Better Auth 的 Google provider；本 slice 要解決的關鍵實作問題是「如何擴增 scope 而不影響既有登入流」。

依 slice-03 design：`meeting.calendar_event_id` 欄位早已存在（NULL by default），就是為了今天填值用。依 slice-04 design：`PlaybookRepository.upsert_for_meeting` 是 playbook 的唯一寫入路徑，不繞道。

## Goals / Non-Goals

**Goals:**

- 使用者授權 Calendar scope 後，從 `/calendar` 頁可看到 24 小時內 events
- 一鍵匯入：建 meeting + LLM 生 playbook 草稿 + 落到編輯器
- 生成保證：稀疏 event（只有 title 一個欄位有值）也要 7 個欄位都產出非空內容
- 錯誤路徑全走 error envelope（既有契約），前端對應 i18n 字串
- TDD：CalendarClient 與 PlaybookGenerator 都用 mocked SDK 寫紅綠重構；6 份 event fixture（rich / sparse / long / zh / en / mixed）每個都得通過「6 結構化欄位皆非空」斷言

**Non-Goals:**

- 第三方 Calendar（Outlook / iCal）
- 雙向同步、webhook、recurring 系列去重
- 從 Gmail / Notion 等拉內容
- 匯入頁行內編輯（仍走 Slice 4 編輯器）
- 自動排程匯入（cron / 背景）
- 客製化 prompt template（固定 v1 prompt）
- LLM streaming response（簡單 await 完整輸出即可）

## Decisions

### Calendar OAuth scope grant flow

採「**獨立 link 流程，不擴充 login scope**」。原因：

1. 既有 Slice 1 的 Google login 只請求 `openid email profile`，許多使用者已登入；要他們重登才加 Calendar scope 體驗差
2. Calendar 是 sensitive scope，登入時順便要會降低同意率
3. Better Auth 的 `linkSocial({ provider: "google", scopes: [...] })` 支援為已登入帳號擴增 scope 並把新 token merge 到 account row

實作：

- `packages/auth/src/server.ts` 加一條 `POST /api/auth/calendar/link`：呼叫 Better Auth 的 `linkSocial` API，scopes 加 `https://www.googleapis.com/auth/calendar.events.readonly`，redirect URL 回 `/calendar`
- `packages/auth/src/server.ts` 加 `GET /api/auth/calendar/status`：回 `{ connected: bool }`，內部讀 Better Auth 的 account row 看 access_token 是否有 calendar scope
- 前端 `/calendar` 頁面在初始 query 失敗（`calendar.not_connected`）時顯示「連結 Calendar」按鈕，按下打 `/api/auth/calendar/link`

Token 儲存：直接沿用 Better Auth 的 `account` 表（`accessToken` / `refreshToken` / `accessTokenExpiresAt` 欄位都已在 Better Auth schema 內），**不另開 `calendar_token` 表**。後端 `CalendarClient` 透過 `pg.Pool` 直查 `account` 表（與 ADR-0025 一致：TS 寫 SQL，Python 端用 SQLAlchemy 讀同一張表也可，但 account 是 Better Auth 的領地，由 TS gateway 提供一個 helper endpoint 給 Python 拿 token 是更乾淨的選項）。**決議**：Python 端透過內部 endpoint `GET /__internal__/users/{id}/calendar-token`（gateway-only，X-Internal-Auth header 帶 shared secret）取得 access_token；access_token 過期時 Python 觸發 `POST /__internal__/users/{id}/refresh-calendar-token`，由 TS 端做 refresh。理由：refresh 邏輯歸 Better Auth 一處管。

### CalendarClient (Python) wraps Google Calendar API

- 檔案：`packages/backend/meeting_playbook/calendar/client.py`
- 依賴：`google-api-python-client`（Calendar API）+ `google-auth`（OAuth credentials 包裝）
- 公開介面：
  - `async get_upcoming_events(user_id: str, hours: int = 24) -> list[CalendarEvent]`
  - `CalendarEvent` dataclass：`id, title, start, end, attendees: list[str], description, organizer`
- 內部流程：
  1. 透過 `TokenStore.get_access_token(user_id)` 拿 token；若回 401（expired），call `TokenStore.refresh(user_id)` 然後重試一次
  2. 用 `googleapiclient.discovery.build("calendar", "v3", credentials=...)` 拉 events.list
  3. 過濾 `timeMin=now, timeMax=now+hours`，order by `startTime`，handle pagination（`pageToken`）直到拿完
  4. 映射 Google response 為 `CalendarEvent` dataclass
- 錯誤映射：
  - HTTP 401 後 refresh 也失敗 → raise `CalendarTokenExpired`（router 對應 `calendar.token_expired`）
  - `httpx.NetworkError` / Google API 5xx → raise `CalendarNetworkError`（router 對應 `calendar.network_error`）
  - 從未 link → `CalendarNotConnected`（router 對應 `calendar.not_connected`）

### TokenStore — Python ↔ TS gateway internal endpoint

- 檔案：`packages/backend/meeting_playbook/calendar/token_store.py` 與 `packages/auth/src/server.ts`
- TS gateway 加兩條 internal endpoints（不掛在 `/api/*` 對 client；改用 `/__internal__/*` 由 gateway 自我消化、需要 `X-Internal-Auth: <secret>` header）：
  - `GET /__internal__/users/:id/calendar-token` → `{ access_token, expires_at }`
  - `POST /__internal__/users/:id/refresh-calendar-token` → 用 refresh_token 走 Google OAuth refresh 端點，更新 account row，回新 access_token
- Python `TokenStore`：用 `httpx` 打這兩條 endpoint（base URL 從 `BACKEND_INTERNAL_AUTH_URL` env 讀，預設 `http://localhost:3001`；shared secret `BACKEND_INTERNAL_AUTH_SECRET` 從 `.env` 讀）
- shared secret 旋轉：env 改值即可，無 DB 狀態

### PlaybookGenerator (deep module) calls Gemini 2.5 Pro on Vertex AI

- 檔案：`packages/backend/meeting_playbook/playbook_generation/generator.py`
- 依賴：`google-genai`（官方 SDK）、`google-cloud-aiplatform` 的 ADC（透過 `GOOGLE_APPLICATION_CREDENTIALS` 服務帳號 JSON）
- 公開介面：
  - `async generate(event: CalendarEvent) -> PlaybookDraft`
  - `PlaybookDraft` TypedDict 與 `PlaybookUpsertPayload` 形狀一致（7 欄位 str），可直接餵給 `PlaybookRepository.upsert_for_meeting`
- 內部流程：
  1. Build prompt（見下節）
  2. 呼叫 `genai.Client(vertexai=True, project=..., location=...)`，model `gemini-2.5-pro`
  3. 用 `response_schema` 強制 LLM 輸出 JSON 物件，欄位剛好是 7 個 string keys（Vertex 的 structured output 模式）
  4. 解析 JSON → `PlaybookDraft`
  5. 若任何欄位空字串 → 觸發 fallback prompt（見下節）重跑一次；第二次仍空 → 填入「（此欄位 LLM 未產出內容，請自行填寫）」localized fallback string
- 錯誤映射：
  - Vertex 5xx / timeout（>30s）→ raise `PlaybookGenerationTimeout`（router → `playbook.generation_timeout`）
  - Schema parse 失敗 → raise `PlaybookGenerationFailed`（router → `playbook.generation_failed`）

### Prompt engineering for sparse events

兩段式 prompt：

- **Primary prompt**（`prompts.py` 中 `BUILD_PRIMARY_PROMPT`）：給 LLM 完整 event metadata（title / attendees / time / description / organizer），要求輸出 JSON 7 欄位，每欄位 markdown 格式、繁體中文為主（依 user locale 切換，但 v1 固定繁中）；明示「即使輸入稀疏也要用對方輪廓 / 預期主題等通用最佳實務填滿 6 個結構化欄位，不可留空」
- **Fallback prompt**（`BUILD_FALLBACK_PROMPT`）：當 primary 任一欄位回空，把空欄位列出來、要求 LLM 純粹基於 event title 推測填充；prompt 限定每個結構化欄位至少 1 句、free_form_markdown 至少 3 行
- 兩段都 force JSON output via Vertex `response_schema`

### REST endpoints

- 檔案：`packages/backend/meeting_playbook/calendar/router.py`
- `GET /api/calendar/upcoming`：query param `hours: int = 24`（min=1 max=168）；回 `list[UpcomingEventRead]`；未連結 → 401 + `calendar.not_connected`（不用 404，因為 user 存在只是 scope 沒給）
- `POST /api/meetings/from-calendar`：body `{event_id: str}`；流程：
  1. 取 event 詳情（再打一次 Calendar API 用 events.get；理由：使用者可能在頁面 idle 期間更動 event）
  2. `MeetingRepository.create(user_id, title=event.summary, counterparty_display_name=organizer.name, me_display_name=user.name, calendar_event_id=event.id)`
  3. `PlaybookGenerator.generate(event)` → draft
  4. `PlaybookRepository.upsert_for_meeting(meeting.id, draft)`
  5. 回 `{meeting_id: str}`
  6. 全部步驟失敗的 partial state：若 step 2 過了但 3 失敗，meeting 已建好但 playbook 沒寫；router 用 try/except 包 step 3-4，失敗時 raise 對應 error_code 但**不回滾 meeting**（使用者進去 meeting detail 仍可看到空 playbook，符合 slice-04 的 auto-create-on-first-read 行為）

### React `/calendar` upcoming events page

- 檔案：`packages/web/src/routes/calendar/upcoming.tsx`
- 包在 `<ProtectedShell>`
- 流程：
  - `useQuery(upcomingEventsQueryOptions(24))` 拉清單
  - 若 query.error 是 `calendar.not_connected` → 顯示「連結 Google Calendar」CTA，點下去打 `POST /api/auth/calendar/link`（auth gateway endpoint，Better Auth 處理 OAuth redirect）
  - 列表每列顯示 title / 開始時間（`toLocaleString` 帶 user locale）/ attendee 數 / 「匯入並生成」按鈕
  - 按下按鈕：`useImportFromCalendarMutation` 跑、按鈕轉 spinner、成功後 `navigate({ to: "/meetings/$id", params: { id: meeting_id } })`
  - 失敗顯示 i18n 對應字串（`errors.calendar.token_expired`、`errors.playbook.generation_timeout` 等）
- `route-tree.tsx` 新增 `/calendar` route
- `routes/meetings/list.tsx` 在 header 「+ 新會議」旁加一個「從 Calendar 匯入」link 連到 `/calendar`

### `lib/calendar-api.ts` query options + mutation hook

- 檔案：`packages/web/src/lib/calendar-api.ts`
- 公開：
  - `getUpcomingEvents(hours): Promise<UpcomingEvent[]>`
  - `importFromCalendar(eventId): Promise<{ meeting_id: string }>`
  - `upcomingEventsQueryOptions(hours)` → queryKey `["calendar", "upcoming", hours]`
  - `useImportFromCalendarMutation()` → 成功 invalidate `["meetings"]`（list refetches 看到新 meeting）
- `CalendarApiError` 與 `MeetingApiError` 共享 base `ApiError` class（這 slice 一併 refactor）

### Test strategy (TDD vertical slice)

- Backend（pytest + httpx async client + 真實 PostgreSQL test DB + mocked Google SDK）：
  - `tests/calendar/test_client.py` — `CalendarClient.get_upcoming_events` 對 mock googleapiclient response：rich list / pagination 兩頁 / 空清單 / 401 一次（觸發 refresh）/ 401 兩次（refresh 失敗 → CalendarTokenExpired）
  - `tests/calendar/test_endpoints.py` — `GET /api/calendar/upcoming` 連結時回 list、未連結回 `calendar.not_connected`；`POST /api/meetings/from-calendar` 完整流程 + ownership（X-User-Id 必填）
  - `tests/playbook_generation/test_generator.py` — 6 份 event JSON fixture，mock `google-genai` client；assert 6 結構化欄位皆非空 + free_form_markdown 至少 3 行；sparse 案例驗 fallback prompt 觸發
  - `tests/playbook_generation/fixtures/{rich,sparse,long,zh,en,mixed}.json`
- Frontend（bun test + happy-dom）：
  - `lib/calendar-api.queries.test.ts` — query options 形狀 + 錯誤映射
  - `lib/calendar-api.mutations.test.tsx` — `useImportFromCalendarMutation` 成功後 invalidate `["meetings"]`
  - `routes/calendar/upcoming.test.tsx` — 渲染 events、未連結顯示 CTA、匯入後 navigate 到 detail
- Auth gateway（bun test）：
  - `__tests__/calendar-link.test.ts` — `POST /api/auth/calendar/link` redirect 包含 calendar.events.readonly scope；internal endpoint shared-secret 驗證

## Risks / Trade-offs

- [Risk] Better Auth 的 `linkSocial` 對「已連結 Google 帳號要加新 scope」可能不支援，需 fork 或自寫 OAuth flow → Mitigation：先在 design 中假設可行；若 apply 階段發現不支援，pivot 為手刻 OAuth 端點（呼叫 Google authorize URL with prompt=consent + access_type=offline，redirect 回 callback 後存 token 進 account row 的 calendarAccessToken / calendarRefreshToken 自加欄位）
- [Risk] Vertex AI Gemini 2.5 Pro 對 sparse event 即使加 fallback prompt 仍可能某欄位空字串 → Mitigation：第二次 fallback 之後仍空就用 i18n string 「（請自行填寫）」充入；測試覆蓋第二次也空的案例
- [Risk] `google-genai` SDK 與 ADC 的 service account 設定不對會在啟動失敗 → Mitigation：`PlaybookGenerator` lazy-init client（首次 call 時建），啟動不檢查；端到端測試裡 mock 整個 client 不踩這條
- [Risk] internal endpoint shared-secret 寫進 .env 若被洩漏，攻擊者可抓任何 user 的 calendar token → Mitigation：endpoint 只 bind 在 127.0.0.1 介面、shared secret 用 `secrets.token_urlsafe(32)` 起始值、文件提示部署時要旋轉
- [Risk] LLM 生成 30s timeout 對 sparse + 長 description 可能不夠 → Mitigation：timeout 改 60s；前端 mutation 也設 60s timeout 並顯示「生成中…可能需 30~60 秒」
- [Risk] meeting 建好但 playbook 生成失敗的 partial state → 已決議**不**回滾 meeting，使用者重進 detail 頁仍能編輯（slice-04 的 auto-create-on-first-read 兜底）；UI 顯示 i18n error，建議使用者「進入 meeting 後手動填或重試生成」
- [Trade-off] 用 Better Auth `account` 表存 calendar token 的優點是不重複造輪子；缺點是 `account` 變成 Python 也要間接讀的表 → 用 internal endpoint 隔離，Python 端不直查

## Migration Plan

1. 若 design 拍板獨立 `calendar_token` 表 → 新 migration `0003_create_calendar_token.py`；本 design 決定**不**走獨立表，所以無 migration
2. `.env.example` 補：`VERTEX_AI_PROJECT`、`VERTEX_AI_LOCATION`（已存在）、`BACKEND_INTERNAL_AUTH_SECRET`、`BACKEND_INTERNAL_AUTH_URL`
3. `pyproject.toml` 加 `google-genai>=1.0`、`google-api-python-client>=2.0`、`google-auth-oauthlib>=1.0`
4. Better Auth 設定：在 `packages/auth/src/auth.ts`（或新檔）為 Google provider 加 `linkScopes` 支援
5. 部署：dev 環境只需 Sean 自己的 Google account 給 Calendar scope；prod 部屬時提示 README 補 Vertex service account 設定
6. 回滾：`git revert` 整批 commit；新表沒有 → 無 schema 回退；環境變數即使不刪也不影響其他 slice

## Open Questions

- Better Auth `linkSocial` 是否支援為已連結帳號加新 scope？決議：apply 第一個 task 就 spike 確認，不可的話走手刻 OAuth flow（已寫進 Risk）
- Vertex AI 的 Gemini 2.5 Pro 在中英混音 prompt 下會不會回多語言混雜結果？決議：v1 prompt 固定要求繁體中文輸出；observe 後再決定是否要 user locale-aware
- 是否要在 `/calendar` 頁面顯示 attendee 名單而不是 attendee 數？決議：v1 顯示「3 人」即可；展開細節留待後續
- 「從 Calendar 匯入」入口要不要也放在登入後的首頁（home）？決議：v1 只放在 `/meetings` list 頭，避免增加 home 頁 surface area

## Decisions added 2026-05-09 (post-smoke ingest)

### Gateway propagates X-User-Name + X-User-Email alongside X-User-Id

The Bun gateway already injects `X-User-Id` for authenticated `/api/*` requests. We extend the same path to inject:

- `X-User-Name`: from `session.user.name` (Better Auth)
- `X-User-Email`: from `session.user.email`

Both are set the same way `X-User-Id` is — overwriting any client-supplied value, applied to non-public `/api/*` routes only. The headers stay scoped to traffic that has already cleared the session check, so they are safe to trust on the FastAPI side.

Why headers (not a database fetch on the Python side): the user row already exists in Postgres but is owned by Better Auth. A second SQL round-trip per request to read user.name / user.email duplicates work the gateway already did. Headers are the cheaper invariant.

### POST /api/meetings/from-calendar uses session identity for both display names

The endpoint accepts the new headers via the existing `get_user_id_dependency` family. Two new dependencies expose `user_name` / `user_email` similarly. The handler picks display names like this:

- `me_display_name` = `X-User-Name` header. Falls back to the email local-part (chars before `@`) if the header is absent. Falls back to `"Me"` only if both header and X-User-Email are absent — which should never happen because the gateway always sets them together.
- `counterparty_display_name` = the first attendee record whose email differs from `X-User-Email`, normalized as `display_name OR email-local-part`. Fallback chain when no other attendee exists:
  1. Event organizer's display name / email
  2. Event title (e.g. course-calendar events with no human attendees)
  3. The string `"Calendar event"` as a last resort

Email comparison is case-insensitive and trims whitespace; both sides are normalized before equality check.

### Out of scope: Markdown rendering in the playbook editor

Smoke testing surfaced that the free-form view renders raw markdown source. That is a Slice 4 (`playbook-management`) UX issue, not a Calendar / LLM concern. A separate change will address it. The slice-05 ingest deliberately does NOT add markdown-rendering tasks.

### Out of scope: non-Google identity providers for Calendar

The Calendar connect flow assumes Google as the OAuth provider. Users without a Google account cannot use Calendar in this slice. Adding Microsoft / Apple Calendar would require a new provider-selection UI plus token-store fan-out and is explicitly not in scope here. The limitation is documented in `docs/agents/calendar.md`.

## Decisions added 2026-05-09 — round 2 (viewer perspective in prompt)

### CalendarEvent gains an organizer_email field

`CalendarEvent.organizer` already carries a display string (Google's `displayName` falling back to email). We add a separate `organizer_email: str` field so the role-classification logic can compare emails without re-parsing the display string. `_event_from_resource` populates it from `item["organizer"]["email"]`, defaulting to the empty string when absent (Google sometimes omits organizer.email for events that come from external feeds — those events get classified as `external` by default).

### PlaybookGenerator.generate signature: (event, viewer_email, viewer_name)

The new positional contract for the generator's only public method is:

```python
async def generate(
    self,
    event: CalendarEvent,
    *,
    viewer_email: str,
    viewer_name: str,
) -> PlaybookDraft
```

`viewer_email` and `viewer_name` are keyword-only on purpose: forcing call sites to name them prevents accidental positional-arg drift if a third viewer field is added later (locale, timezone, etc.).

Empty `viewer_email` is allowed but degrades the role classification to `external`. Empty `viewer_name` falls back to the email's local-part when filling the prompt; if both are empty, the prompt names the viewer as `"the user"` and warns the model that viewer identity is unknown.

### Role classification

A new pure helper `meeting_playbook.calendar.identity.classify_viewer_role(event, viewer_email) -> Literal["organizer", "attendee", "external"]`:

- Returns `"organizer"` when `viewer_email` (case-insensitive, trimmed) equals `event.organizer_email`
- Returns `"attendee"` when `viewer_email` matches the email portion of any entry in `event.attendees` (parsed with the existing `_parse_attendee` helper) AND does not match the organizer
- Returns `"external"` otherwise (including the case where the viewer's email is the organizer's but `organizer_email` is empty — without an organizer email to compare against, we cannot promote to organizer)

The function lives next to `pick_counterparty` because both are pure utilities about viewer-vs-event identity. Tests parametrize across the three branches plus edge cases (case mismatch, whitespace, empty viewer_email, empty organizer_email).

### Prompt prelude

`build_primary_prompt` and `build_fallback_prompt` both gain a leading paragraph generated by a new private helper `_render_viewer_block(event, viewer_email, viewer_name)`:

```
You are preparing this playbook for {viewer_name} ({viewer_email}).
In this meeting their role is: {role}.
{role-specific guidance line}
The other parties are: {others list}.
Write the playbook from {viewer_name}'s point of view — every field should
read as advice / preparation FOR {viewer_name}, not as a third-person summary.
```

Role-specific guidance line:
- `organizer` — "They are hosting / driving this meeting; objectives and talking_points should reflect what they want to achieve and how they want to lead the discussion."
- `attendee` — "They were invited by someone else; objectives and talking_points should reflect what they need to learn / contribute as a participant, and what questions to ask."
- `external` — "They are previewing this event from a calendar they subscribe to but were not personally invited; the playbook should help them decide what to take away from observing the meeting."

`others list` excludes the viewer's own email (case-insensitive). When the viewer is `external`, the others list includes the organizer plus all attendees.

### Router: pass session identity into the generator

`POST /api/meetings/from-calendar` already reads `X-User-Email` and `X-User-Name` via the existing `get_user_email_dependency` and `get_user_name_dependency` (added in round 1). The router now passes both into `generator.generate(event, viewer_email=..., viewer_name=...)`. No new dependencies are introduced.

### Test impact

- `tests/playbook_generation/test_generator.py` — every existing parametrized case now passes `viewer_email`, `viewer_name` keyword args. Add three new role-specific cases: organizer-perspective produces text that mentions hosting / driving language, attendee-perspective produces participant / asking language, external-perspective produces observer language. Each new case asserts that the rendered prompt (capturable via the injected `call_model` callback) contains the role-specific guidance line and the viewer's name.
- `tests/calendar/test_endpoints.py` — the four ingest-round-1 scenarios now also assert that the generator was invoked with the correct viewer_email and viewer_name from the X-User-* headers. Add one new role-classification end-to-end case: an event where the viewer is `external` (subscribed-calendar event) imports successfully and the generator received `viewer_email` matching the X-User-Email header.
- `tests/calendar/test_classify_viewer_role.py` — new parametrized file mirroring `test_pick_counterparty.py` for the three branches plus edge cases.
- `tests/calendar/test_client.py` — `_make_event_resource` adds `organizer={"email": ..., "displayName": ...}` so `_event_from_resource` populates `organizer_email`. Existing assertions on returned `CalendarEvent` are extended where they care.

### Out of scope (still)

Markdown rendering in the playbook editor remains deferred to a separate change (per round-1 ingest). Round-2 changes do NOT touch the editor surface. The improved prompt only affects the LLM-generated content text; rendering of that text is still raw markdown in the textarea.
