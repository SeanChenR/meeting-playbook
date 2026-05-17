## Context

Slice-05 落地當下，calendar 匯入做成 fire-and-forget：`POST /api/meetings/from-calendar` 一個 request 內完成「fetch event → 建 meeting row → 跑 Playbook 生成 → 寫 playbook row → 回 `{meeting_id}`」。當時還沒有 attachment 概念，使用者沒有什麼可以在生成前提供的，這個流程合理。

Slice-20a 把 attachment（會議的補充檔案 / 文件）能力做進來。但 attachment 必須在 Playbook 生成**之前**就 attach 上 meeting，generator prompt 才會把附件內容（或檔名摘要）納入考慮。Calendar 匯入這條路徑現在就卡住了：使用者一按「匯入」立刻就 fire 生成，沒機會掛附件。

順帶解掉兩個既有痛點：(1) `pick_counterparty` 在多 attendee 情境下會留空（沒人能被唯一指定為對方），目前流程一旦匯入完成才能編，使用者要先看到很糟的 Playbook 才知道要改；(2) `me_display_name` 目前固定塞 login user 的 `name`，多帳戶或暱稱情境下使用者沒機會調整。

預覽表單把這三件事一次解掉：匯入 = navigate 至既有 `/meetings/new`，預填 calendar 欄位 + 顯示 attachment 區塊，使用者調整完按「建立」才觸發生成。

## Goals / Non-Goals

**Goals:**

- 把 Calendar 匯入從 fire-and-forget 改成 preview-and-confirm，並讓 Playbook 生成在使用者明確 confirm 之後才跑。
- `POST /api/meetings` 變成「建 meeting + 可選觸發 Playbook 生成 + 可選 attach 既有 attachments」的單一收斂端點；既有「手動 create 空 playbook」路徑零影響。
- 既有 `/meetings/new` 路由直接複用：preview 不是新頁面、不是 modal、不是 wizard。
- 既有 calendar-domain error code（`calendar.not_connected` / `calendar.token_expired` / `calendar.network_error`）在新單一 event endpoint 沿用。

**Non-Goals:**

- 不引入背景 job 或 retry queue — Playbook 生成同步走 `POST /api/meetings` 的 response cycle（既有 60s timeout + error code 維持）。
- 不在 preview 階段 dry-run Playbook 生成 — 只有「建立」按下後才會跑生成。
- 不調 `pick_counterparty` 演算法 — 多 attendee 仍留空讓使用者手動填。
- 不開放 attach 既有別場會議的 attachment（S20a 規則：attachment 一旦 attach 就鎖住）。
- 不寫回 Google Calendar — 預覽表單編輯只影響本地 meeting，不同步回 calendar event。
- 不處理 calendar event 同 id 重覆匯入（既有 `calendar_event_id` 沒 unique constraint，本 slice 不加，重覆匯入會建立兩筆不同 meeting，跟既有行為一致）。

## Decisions

### Endpoint 拆分：保留 `POST /api/meetings` 為單一 create entry point，廢 `POST /api/meetings/from-calendar`

把 calendar import 收進 `POST /api/meetings` 而不是另外新增 `POST /api/meetings/from-calendar-preview-confirm` 或類似端點。理由：(a) 端點數量少一個、(b) 前端只需要知道一個 create endpoint、(c) `attachments[]` 邏輯在 calendar 與非 calendar 兩條路徑共用 — 反正都是「create meeting 後把 nullable attachment.meeting_id 寫回新建 meeting_id」。

廢 `POST /api/meetings/from-calendar` 改回 HTTP 410 Gone 配 `error_code: calendar.import_endpoint_removed`，body message 提示前端改 navigate 至 `/meetings/new?from_calendar=<id>`。理由：徹底斷舊路徑、舊版前端 cache 還在跑時也會立刻看到清楚錯誤。**Alternative considered**：留舊 endpoint 做 server-side redirect 至新流程 — 被否決，server 無法替使用者 fill 表單，redirect 後使用者反而 confused；前端版本不一致時直接報錯比較好 debug。

### Calendar event detail：新 `GET /api/calendar/events/{event_id}`，不重用 `/upcoming` 列表

`/upcoming` 是 time-windowed batch fetch，前端要從列表挑出單一 event 必須先傳回整個列表。預填表單只需要單一 event 的 detail（且必須包含 `description` 與完整 attendees — 列表為了省 payload 可能裁掉）。所以另開 `GET /api/calendar/events/{event_id}` endpoint，呼叫 `CalendarClient.get_event(event_id)`（slice-05 既有；目前只被 `POST /api/meetings/from-calendar` 內部呼叫）。回 schema 跟 `CalendarEvent` model 一致（id / title / start / end / description / attendees / organizer），attendees 維持 slice-07 resource-filter 規則。**Alternative considered**：擴 `/upcoming` 加 `event_id` query — 被否決，會把列表 fetch 跟單一 detail fetch 混在同一個 endpoint，response shape 變條件式，前端難用。

Calendar-domain error code 沿用 slice-05 既有 3 個（`calendar.not_connected` / `calendar.token_expired` / `calendar.network_error`）+ 新增一個 `calendar.event_not_found`（404，跟「不洩漏其他人 event 存在」規則一致）。

### Playbook 生成觸發點下移至 `POST /api/meetings`

舊路徑：`POST /api/meetings/from-calendar` 內部直接呼叫 generator + 寫 playbook row。新路徑：`POST /api/meetings` body 帶 `calendar_event_id` 時，meeting 寫完之後同 request 內呼叫 generator → 寫 playbook row → 回 `{meeting_id, playbook_id, status}`。觸發條件 = `calendar_event_id IS NOT NULL`（簡單明確，前端決定觸發與否就是「帶不帶」）。

router 編排順序（同一 transaction 內）：(1) validate body、(2) 若 `calendar_event_id` 非 null，先 `CalendarClient.get_event(event_id)` 拿 event detail（為了給 generator）— 若 calendar fetch 失敗 → 回 calendar-domain error code、meeting 不建、attachment 不 attach；(3) `MeetingRepository.create(...)` 建 meeting row（含 schedule、calendar_event_id）；(4) 若 `attachments[]` 非空，驗證 ownership + 未 attach + 把每個 attachment row 的 `meeting_id` 從 null 寫成新建 meeting_id（單一 transaction）— 任一驗證失敗 → rollback meeting + 回 attachment-domain error code；(5) 若 `calendar_event_id` 非 null → call generator → 寫 playbook row（沿用 slice-05 既有錯誤處理：generator timeout/failed 時 meeting + attachments 已寫入，僅 playbook 失敗）。

**Alternative considered**：分兩個 round-trip — 前端先 `POST /api/meetings` 建空 meeting + attach attachments、收到 meeting_id 後再 `POST /api/meetings/{id}/playbook/generate` — 被否決，多一個 round-trip、前端要處理中間態（meeting 建好但 playbook 還沒）、且若第二步失敗 meeting 已在 list 裡留下「無 Playbook」的孤兒 row。**Alternative considered**：保留 `POST /api/meetings/from-calendar` 做 router thin wrapper 內部 call `POST /api/meetings` — 被否決，留 dead path 容易讓未來 reader 以為兩條路徑並存。

### 前端：擴 `/meetings/new` 路由讀 `?from_calendar=<event_id>` query

預覽表單 = 既有 `/meetings/new`（slice-03 落地）+ S20a attachment 區塊 + URL query 預填 + create payload 帶 `calendar_event_id`。沒有新路由、沒有 modal。

預填策略：route 進來時若 `from_calendar` query 存在 → tanstack-query `getCalendarEvent(eventId)` 抓 detail → useEffect 把表單 default 值塞入。Defaults：`title = event.title`、`scheduled_start_at = event.start`、`scheduled_end_at = event.end`、`description` 欄位（若 form 有）= `event.description`、`me_display_name = currentUser.name`、`counterparty_display_name = pick_counterparty(event.attendees, currentUser.email)`（共用 slice-05 既有 picker 行為，多 attendee → 留空、單一 non-viewer human → 用其 displayName）。表單欄位仍 fully editable — 預填只是 default。

預填過程中顯示 banner「正在從 Calendar 預填欄位…」；fetch 失敗 → banner 改顯 localized error（沿用 `localizedErrorMessage(error.error_code, t)`）+ 把預填邏輯 skip 掉，使用者可手動填欄位。**Alternative considered**：失敗就 navigate 回 `/calendar/import` 顯 toast — 被否決，使用者已經在 form 上，把錯誤就近顯示比 reload 更不擾。

### Attachment 預覽掛載：在 meeting 建立**之前** stage

S20a 把 attachment row 上傳完成後 `meeting_id` 為 null（pending），使用者按「建立」之前都還掛在 user scope 內。預覽表單顯示的 attachment 區塊 list 出該 user 名下所有 `meeting_id IS NULL` 的 attachment（S20a 預設行為）；使用者勾選要在這場 meeting 用的 attachment，submit 時把選中的 attachment id 陣列傳進 `POST /api/meetings` body 的 `attachments[]`。

backend `POST /api/meetings` 收到 `attachments[]` 後對每個 id 驗：(a) 屬 current user、(b) `meeting_id IS NULL`。任一條件失敗 → rollback meeting create + 回 `attachment.not_attachable` 422。**Alternative considered**：「在 `/meetings/new` route 內也允許使用者直接上傳新 attachment」— 被否決，會把上傳 UI 跟 meeting create 兩條 lifecycle 糾在一起；目前 staged attachment list 已足夠，使用者要新上傳可去 attachment 上傳區（S20a 落地）再回 preview。

### ADR-0027 amendment（不開新 ADR）

ADR-0027 主題是「Calendar OAuth scope 經 Better Auth `linkSocial` 授權」— S20b 動的是「匯入後做什麼」這層，沒有更動 scope / token / auth 機制。所以**附 amendment 段落**在 ADR-0027 末尾（「Amended by slice-20b」），記錄 import 流程拆分；不另開 ADR-0028+。**Alternative considered**：開新 ADR「Calendar import preview vs auto-create」— 被否決，ADR-0027 已涵蓋 scope-link 與 import-as-a-flow 兩個面向，分裂為兩個 ADR 後 future reader 反而要追兩篇；amendment 段落足以記錄。

## Implementation Contract

- **Observable behavior**：
  - 使用者在 `/calendar/import` 點任一 event 的「匯入」按鈕 → 瀏覽器 navigate 至 `/meetings/new?from_calendar=<event_id>`（不 fire 任何 POST）。
  - `/meetings/new?from_calendar=<event_id>` 載入時，title / scheduled_start_at / scheduled_end_at / me_display_name / counterparty_display_name 顯示為預填值；表單欄位仍可編輯；S20a attachment 區塊顯示該 user 名下所有 pending（`meeting_id IS NULL`）attachment 並可勾選。
  - 使用者按「建立」→ `POST /api/meetings` body 含 `calendar_event_id` + `attachments[]` + 表單 3 個必填欄位（title / counterparty_display_name / me_display_name）+ optional schedule。response 201 含 `{meeting_id}`；之後 navigate 至 `/meetings/{id}` 顯示 Playbook 已生成。
  - 既有路徑 `POST /api/meetings/from-calendar` 回 HTTP 410 Gone + `error_code: calendar.import_endpoint_removed`。

- **API contracts**（新增 / 修改）：
  - `GET /api/calendar/events/{event_id}` → `200 CalendarEventDetail`：`{id, title, start: ISO8601 | null, end: ISO8601 | null, description: string | null, attendees: Attendee[], organizer: Organizer | null}`（attendees 已去 resource）。錯誤：`calendar.not_connected` 401、`calendar.token_expired` 401、`calendar.event_not_found` 404、`calendar.network_error` 502。
  - `POST /api/meetings` request body 從既有 3 必填 + 既有 ASR / schedule optional 欄位，**新增** `calendar_event_id?: string` 與 `attachments?: string[]`。回應 201 維持 `MeetingRead` shape；若 `calendar_event_id` 非 null 且 generator 失敗，meeting 仍寫入 + response 改為 generator 既有 error envelope（`playbook.generation_timeout` 504 / `playbook.generation_failed` 502）— 跟 slice-05 既有 from-calendar 路徑語意一致。
  - `POST /api/meetings/from-calendar` → HTTP 410 Gone，body `{error_code: "calendar.import_endpoint_removed", message: ...}`。

- **Failure modes**：
  - Calendar fetch 失敗（preview load 階段）→ banner 顯示 localized error，表單仍可手動填，使用者可繼續建立非 calendar 路徑 meeting（不傳 `calendar_event_id` 即可）。
  - Submit 時 attachment 已被別場會議搶走 → 422 `attachment.not_attachable`，meeting 不建，前端 refetch attachment list。
  - Submit 時 generator 失敗 → meeting + attachments 已寫入（DB committed），response 504/502 配 generator error code；前端 navigate 至 `/meetings/{id}` 顯示「Playbook 生成失敗，可手動編輯」。

- **Acceptance criteria**：
  - Backend tests：(a) `GET /api/calendar/events/{event_id}` happy path 回完整 detail、(b) `GET /api/calendar/events/{event_id}` 對未登入 calendar / event 不存在 / token expired 各回對應 error code、(c) `POST /api/meetings` 帶 `calendar_event_id` 觸發 generator + 寫 playbook row、(d) `POST /api/meetings` 帶 `attachments[]` 把 attachment row 的 meeting_id 寫回、(e) `POST /api/meetings` `attachments[]` 含他 user 的 id 回 422 + meeting 不建、(f) `POST /api/meetings/from-calendar` 回 410。
  - Frontend tests：(a) `/meetings/new?from_calendar=evt_1` mount 觸發 `getCalendarEvent` query + 預填 title / counterparty / me display name、(b) 多 attendee event 載入時 counterparty 欄位留空、(c) `/calendar/import` 點匯入按鈕 navigate 至 `/meetings/new?from_calendar=...`（不 fire POST）、(d) submit 帶 `calendar_event_id` + 選中的 `attachments[]`、(e) calendar fetch 失敗時 banner 顯示 localized error 且表單仍可送出。
  - Spec deltas validate via `spectra validate slice-20b-calendar-import-preview`。
  - i18n `locales.test.ts` deep-equal 通過。

- **Scope boundaries**：
  - In scope：calendar router 廢舊端點 + 加單一 event endpoint、meeting router create endpoint 擴 `calendar_event_id` + `attachments[]`、`/meetings/new` 預填 + attachment 區塊整合、ADR-0027 amendment、calendar-integration / playbook-generation / meeting-management spec deltas、i18n 雙 locale。
  - Out of scope：S20a attachment capability 本體（屬 S20a；S20b 只調用既有 attachment row 寫回 meeting_id 的能力）、新背景 job / queue、Calendar 寫回、`pick_counterparty` 演算法調整、meeting list / detail 顯示 attachment 區塊（S20a 已處理；本 slice 不擴）。

## Risks / Trade-offs

- **Risk**：generator 失敗時 meeting + attachments 已 committed，使用者看到一個「無 Playbook 的 meeting」。**Mitigation**：沿用 slice-05 既有錯誤處理 — generator 失敗 response 直接 surface error code，前端 navigate 至 `/meetings/{id}` 顯示「Playbook 生成失敗，可手動編輯」（slice-04 auto-create 空 playbook 仍生效，meeting 不是孤兒）。
- **Risk**：使用者在 preview 表單 stage 一些 attachment 但沒按「建立」就離開 — pending attachment（`meeting_id IS NULL`）會留在資料庫。**Mitigation**：屬 S20a lifecycle（pending attachment 清理 / GC 規則 S20a 負責定義），S20b 不額外加 cleanup 邏輯。
- **Risk**：使用者重覆匯入同一個 calendar event → 建立兩筆 meeting 共用同 `calendar_event_id`。**Mitigation**：跟既有 from-calendar 行為一致（既有 `calendar_event_id` 無 unique constraint），S20b 不改，後續 slice 若要做 idempotency 再開獨立 change。
- **Risk**：前端版本還在跑舊 `importFromCalendar` mutation 時，後端已部署 410。**Mitigation**：410 response 含 localized error message 指引使用者重新 load 頁面；前端在 react-query error handler 內偵測 `calendar.import_endpoint_removed` 觸發 `window.location.reload()` 取得新版前端。
- **Trade-off**：把 `calendar_event_id` 觸發條件放進 `POST /api/meetings` 讓單一 endpoint 行為條件化 — 換來前端 / 後端契約簡化（一個 create endpoint）+ attachment 邏輯共用。

## Migration Plan

- 既有 archive 過的 slice-05、slice-07 spec 條目改寫 / 標 deprecated 透過本 slice 的 modified spec deltas 落地。
- 部署順序：(1) 後端先 ship 新 `GET /api/calendar/events/{event_id}` + `POST /api/meetings` 擴欄位 + `POST /api/meetings/from-calendar` 改 410；(2) 前端 ship `/calendar/import` 改 navigate + `/meetings/new` 預覽流程；(3) 兩端 ship 之間若舊前端打到新 410，error handler 觸發 reload，使用者重新拿到新前端。
- Rollback：把後端 `POST /api/meetings/from-calendar` 從 410 改回原 slice-05 實作（router 程式碼留 git history 一個 revert commit）；前端把 `/calendar/import` import 按鈕改回 fire mutation。Rollback 不會留 schema migration（本 slice 純路由與 schema 欄位 optional 化，無 DB schema 變更）。
- 既有 calendar_event_id 已有資料的 meeting 不受影響（本 slice 不動既有 row）。

## Open Questions

- generator 失敗時是否還要把 `attachments[]` 已寫入 meeting_id 的 row「rollback 回 null」？目前傾向**不 rollback**（meeting 仍存在，attachment 跟著 meeting 走），但 apply 階段確認 user 期待後若要改成 rollback，會反映在 tasks。
- 前端 attachment 區塊顯示是否要做「在 preview 表單內直接上傳新 attachment」UI 捷徑？目前傾向**沒有**（保持 staged-list-only），apply 階段 user feedback 可調。
- 410 response 是否需要在 body 內帶「請改 navigate 至 X」的 URL hint？目前傾向 error message 文字提示足夠；apply 階段若需要結構化 hint 再加。
