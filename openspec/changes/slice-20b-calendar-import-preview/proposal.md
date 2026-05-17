> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/27
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
> Depends on: slice-20a-meeting-attachment（須先 archive，preview 表單才有附件 capability 可掛）

## Why

目前 Calendar 匯入是 fire-and-forget：使用者在 `/calendar/import` 點一下，後端立即 `POST /api/meetings/from-calendar` 建立 meeting 並 fire Playbook 生成，使用者沒有機會在生成前先掛附件、調 me / counterparty display name、或在多 attendee 情境下指定誰是對方。S20a 已導入 attachment capability，必須在「meeting 建立 + Playbook 生成」**之前**讓使用者把附件掛上去，否則附件無法影響 LLM 產出的 Playbook。S20b 把流程改成 preview-and-confirm：匯入只是把 calendar event 預填到 `/meetings/new` 表單，使用者調整 + 掛附件後按「建立」才真正觸發 meeting create + Playbook 生成。

## What Changes

- **BREAKING**：廢除 `POST /api/meetings/from-calendar`（既有路徑，slice-05 落地）。endpoint 改回 HTTP 410 Gone 配 `error_code: calendar.import_endpoint_removed`；既有前端 calendar import 觸發路徑改為 navigate 至 `/meetings/new?from_calendar=<event_id>` 而非 fire `POST`。
- **BREAKING**：Playbook 生成觸發點從 `POST /api/meetings/from-calendar` 移至 `POST /api/meetings`（只在 request 帶 `calendar_event_id` 時觸發）。既有非 calendar 路徑（手動 create）的行為不變，仍走 slice-04 auto-create 空 playbook。
- 新增 `GET /api/calendar/events/{event_id}`：讀單一 calendar event detail（title / start / end / description / attendees / organizer），供 `/meetings/new` 預填用。沿用 slice-05 既有 `CalendarClient.get_event` 邏輯與 resource-attendee 過濾規則。
- 擴 `POST /api/meetings` request schema：新增兩個 optional 欄位 — `calendar_event_id: string | null`、`attachments: string[]`（已上傳到 S20a 的 attachment id 列表）。`calendar_event_id` 非 null 時：(a) 寫入 meeting row 對應欄位、(b) 觸發 Playbook 生成（既有 slice-05 generator + prompt 路徑）。`attachments` 非空時：把每個 attachment id 對應的 row `meeting_id` 從 null 改成新建的 meeting id（ownership 驗證：每個 attachment 須屬 current user 且尚未 attach）。
- 擴 `/meetings/new` 路由：讀 query param `from_calendar=<event_id>`。若存在 → `GET /api/calendar/events/<event_id>` 拿 detail → 預填 `title` / `scheduled_start_at` / `scheduled_end_at` / `description`（若 backend schema 已有對應欄位則寫入）/ `me_display_name = current user.name` / `counterparty_display_name = pick_counterparty(attendees, viewer_email)`（沿用 slice-05 既有 picker；無唯一非 viewer human attendee 時留空）。表單顯示 S20a attachment 區塊讓使用者上傳。送出 = `POST /api/meetings` with `{calendar_event_id, attachments[]}`。
- 修訂 ADR-0027（**Amended by slice-20b**）：把原本「import = build meeting + generate Playbook」流程拆成「import = navigate to preview form」+「create endpoint = build meeting + generate Playbook」。Amendment 段落寫明分離理由（user 需要在生成前 attach 檔案 + 校 display name），既有 `linkSocial` scope 機制不變。
- 修訂 `openspec/specs/calendar-integration/spec.md`：移除 `POST /api/meetings/from-calendar` requirement，新增 `GET /api/calendar/events/{event_id}` 取單一 event detail requirement。修訂 `openspec/specs/playbook-generation/spec.md`：Playbook 生成觸發點從 calendar import endpoint 改為 `POST /api/meetings`（帶 `calendar_event_id` 時）。修訂 `openspec/specs/meeting-management/spec.md`：`POST /api/meetings` request body 新增 `calendar_event_id` 與 `attachments[]` optional 欄位 + 對應的 Playbook 觸發與附件關聯規則。
- i18n：`/meetings/new` 新增 calendar pre-fill UX 對應字串（pre-fill banner、multi-attendee counterparty 待定提示、import error fallback）。zh-TW + en 雙 locale 同步。

## Non-Goals

- 不調整 attachment 的型別 / 大小 / 數量限制 — 完全沿用 S20a 既有規則。
- 不引入 multi-step wizard — 預覽就是既有 `/meetings/new` 路由 + URL query 預填，不另開頁面。
- 不在 preview 階段預跑 Playbook 生成「dry run」preview — 生成只在「建立」按下後跑一次。
- 不處理 Google Calendar 那端的事件編輯（這支只讀 + 預填，不寫回 Calendar）。
- 不調 `pick_counterparty` 演算法（slice-05 已落地；多 attendee 仍留空，使用者手動填）。
- 不新增 background job / retry queue — Playbook 生成仍同步走 `POST /api/meetings` 的回應週期；既有 generator timeout / failed error codes 沿用。
- 不開放 attach 既有別場會議的 attachment（attachment 一旦 attach 到某 meeting 就鎖住，S20a 規則維持）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `calendar-integration`：(BREAKING) 移除 `POST /api/meetings/from-calendar` 一次完成 meeting + Playbook 的契約；新增 `GET /api/calendar/events/{event_id}` 單一 event detail 端點供前端預填。
- `playbook-generation`：(BREAKING) 生成觸發點從 calendar import endpoint 改為 `POST /api/meetings`（當 request 帶 `calendar_event_id` 時）。
- `meeting-management`：(BREAKING) `POST /api/meetings` 接受 optional `calendar_event_id` 與 `attachments[]`，並在帶 `calendar_event_id` 時於同一 request 內觸發 Playbook 生成；既有 calendar_event_id 在 create 階段固定為 null 的規則被本 slice 取代。

## Impact

- Affected ADRs:
  - Amended: `docs/adr/0027-calendar-scope-link.md`（新增 "Amended by slice-20b" 區段，記錄 import 流程拆分）
- Affected specs:
  - Modified: `openspec/specs/calendar-integration/spec.md`
  - Modified: `openspec/specs/playbook-generation/spec.md`
  - Modified: `openspec/specs/meeting-management/spec.md`
- Affected code:
  - Modified: `packages/backend/meeting_playbook/calendar/router.py`（廢 `POST /api/meetings/from-calendar` 改回 410；新 `GET /api/calendar/events/{event_id}`）
  - Modified: `packages/backend/meeting_playbook/calendar/schemas.py`（新增 single-event response schema）
  - Modified: `packages/backend/meeting_playbook/meetings/router.py`（`POST /api/meetings` 接 `calendar_event_id` + `attachments[]`，編排 Playbook 生成 + attachment attach）
  - Modified: `packages/backend/meeting_playbook/meetings/schemas.py`（`MeetingCreate` 加 optional 欄位）
  - Modified: `packages/backend/meeting_playbook/meetings/repository.py`（create 接受 `calendar_event_id` 與 schedule 欄位）
  - Modified: `packages/web/src/routes/meetings/new.tsx`（讀 `from_calendar` query → 預填表單 → 顯示 attachment 區塊 → submit 帶 `calendar_event_id` + `attachments[]`）
  - Modified: `packages/web/src/routes/calendar/upcoming.tsx`（「匯入」按鈕從 `POST` 改為 `navigate("/meetings/new?from_calendar=...")`）
  - Modified: `packages/web/src/lib/calendar-api.ts`（新 `getCalendarEvent(eventId)` query；移除既有 `importFromCalendar` mutation）
  - Modified: `packages/web/src/lib/meetings-api.ts`（`createMeeting` request type 加 optional `calendar_event_id` + `attachments[]`）
  - Modified: `packages/web/src/locales/zh-TW.json`、`packages/web/src/locales/en.json`（新增 preview / pre-fill / multi-attendee 提示字串）
  - Modified: `docs/adr/0027-calendar-scope-link.md`（amendment 區段）
  - New: `packages/backend/tests/calendar/test_get_event_endpoint.py`（單一 event detail 端點 tests）
  - Removed: `packages/web/src/lib/calendar-api.mutations.test.tsx` 內 `importFromCalendar` 相關案例（改寫成 `getCalendarEvent` query test）
- New env vars: (none — 沿用既有 calendar / playbook generator 變數)
