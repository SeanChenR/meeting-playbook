## Context

Slice 3 已交付 Meeting CRUD（schema + REST + 3 個 React route）。每場 meeting 在 detail 頁只顯示 metadata；playbook 是 PRD 的核心會前資產，需要使用者填入 6 個欄位的會議準備內容（objective / counterparty profile / anticipated topics / anticipated objections / talking points / red lines），加上自由發揮的 free-form markdown body。

Slice 5（Issue #7）會用 Gemini 2.5 Pro 從 Calendar event 自動生成 playbook，因此本 slice 必須先把資料層 + 編輯器立起來、保留「自動寫入這 7 個欄位」的擴充點。Slice 6 advisor 與 Slice 8 in-meeting 顯示也都讀這份 playbook。

依 ADR-0012 / ADR-0021 / ADR-0025：Alembic 管應用表，FastAPI 不自證 session（信任 `X-User-Id`），TS 端不引 ORM。依 slice-03 確立的「MeetingRepository 為 meeting 的唯一存取路徑」原則，本 slice 透過 `MeetingRepository.get_for_user` 做 ownership gate，不直接 query meeting table。

## Goals / Non-Goals

**Goals:**

- Playbook 與 meeting 1:1 關係（UNIQUE meeting_id），ownership 透過 meeting 推導，不另設一條 ACL
- `GET /api/meetings/{id}/playbook` 永遠 200：第一次讀觸發 row 自動建立（empty strings），使用者進入畫面就有可編輯表面
- `PUT /api/meetings/{id}/playbook` 是 full upsert：客戶端提供完整 7 欄位，缺漏視為空字串；不做 PATCH 半量
- React `PlaybookPane` 雙視圖（free-form / structured），toggle 不丟失未存檔的兩邊內容
- 編輯器使用 plain `<textarea>`（v1 不引第三方 markdown 套件）
- 透過 TanStack Query：`playbookQueryOptions(meetingId)` + `useUpsertPlaybookMutation`，存後 invalidate
- 中英混用 markdown 內容能正確顯示與儲存
- TDD vertical slice：repository / endpoints / 元件三層各自紅綠

**Non-Goals:**

- LLM 自動生成（Slice 5）
- Versioning / undo / history
- 即時協作（多人同編）
- 會議進行中即時同步顯示（Slice 8）
- Markdown 預覽 / wysiwyg / side-by-side
- Templating system；一律從空 row 開始
- 第三方 markdown editor 元件（如 @uiw/react-md-editor）；v1 用 textarea

## Decisions

### Alembic migration: playbook table schema

- 檔案：`packages/backend/alembic/versions/0002_create_playbook.py`
- 欄位：
  - `id` TEXT PRIMARY KEY（`secrets.token_urlsafe(16)`，前綴 `pb_`）
  - `meeting_id` TEXT NOT NULL，FK → `meeting.id` ON DELETE CASCADE
  - `free_form_markdown` TEXT NOT NULL DEFAULT `''`
  - `objective` TEXT NOT NULL DEFAULT `''`
  - `counterparty_profile` TEXT NOT NULL DEFAULT `''`
  - `anticipated_topics` TEXT NOT NULL DEFAULT `''`
  - `anticipated_objections` TEXT NOT NULL DEFAULT `''`
  - `talking_points` TEXT NOT NULL DEFAULT `''`
  - `red_lines` TEXT NOT NULL DEFAULT `''`
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`（trigger 在 PUT 時手動 set，不靠 DB trigger）
- Constraint：`UNIQUE(meeting_id)` — 一場會議只有一份 playbook
- Index：UNIQUE 已建索引；無額外 index（讀取一律走 meeting_id 點查）
- 不使用 PG ENUM / 不使用 JSON 欄位儲六大欄位 — 用獨立 TEXT 欄位讓 LLM 在 Slice 5 直接 set 單欄、也方便未來 partial 更新

### PlaybookRepository (async SQLAlchemy 2.0) as the single access path

- 檔案：`packages/backend/meeting_playbook/playbooks/{models,repository,schemas}.py`
- `models.Playbook`: `MappedAsDataclass` 風格，七個 markdown 欄位皆 `Mapped[str]`；`updated_at: Mapped[datetime]`
- `repository.PlaybookRepository`：建構子吃 `AsyncSession`；公開 method：
  - `async get_or_create_for_meeting(meeting_id: str) -> Playbook` — 不存在則 INSERT 後回傳；存在直接 SELECT。整段在一個 transaction 內，避免 race
  - `async upsert_for_meeting(meeting_id: str, payload: PlaybookUpsertPayload) -> Playbook` — UPSERT 七個欄位 + 寫 `updated_at = now()`；採用 `INSERT ... ON CONFLICT (meeting_id) DO UPDATE` 一條 SQL 完成
- 後續 slice（advisor / summary）一律走這個 repo，不直接 query playbook table

### FastAPI router with ownership gate via MeetingRepository

- 檔案：`packages/backend/meeting_playbook/playbooks/router.py`，server.py mount `prefix=""`（router 內部宣告 `/api/meetings/{meeting_id}/playbook`）
- 共用 dependency：`get_user_id_dependency`（沿用 slice-03）
- 流程（GET 與 PUT 共享）：
  1. `MeetingRepository.get_for_user(user_id, meeting_id)` — 找不到回 404 + `error_code: meeting.not_found`（與 slice-03 一致，不洩漏存在）
  2. 若存在 → 呼叫 `PlaybookRepository.{get_or_create,upsert}_for_meeting(meeting_id)`
  3. 回 `PlaybookRead`
- Pydantic schemas（`schemas.py`）：
  - `PlaybookUpsert`：所有 7 欄位皆 `str = ""` 預設；後端 strip whitespace 但允許空字串（不像 meeting title 要求 min_length=1）
  - `PlaybookRead(id, meeting_id, free_form_markdown, objective, counterparty_profile, anticipated_topics, anticipated_objections, talking_points, red_lines, created_at, updated_at)`
- 不做 `PATCH` — 整份 PUT 比較簡單、與 PRD 一致
- 缺 `X-User-Id` header → 401 + `auth.gateway_bypass`（沿用既有 dependency）

### PlaybookPane React component with view-mode toggle

- 檔案：`packages/web/src/components/playbook-pane.tsx`
- props：`{ meetingId: string }`
- 內部 state：
  - `view: "freeform" | "structured"`（local React state）
  - 7 個欄位的暫存值（local React state，初始值來自 query.data；切 view 不重設）
- 資料層：
  - `useQuery(playbookQueryOptions(meetingId))` — 取得當前 row
  - `useUpsertPlaybookMutation(meetingId)` — 存檔；onSuccess 後 invalidate `["playbook", meetingId]`
- UI：
  - 頂部 segmented toggle：`[ 自由格式 | 結構化 ]`（呼應 `LocaleToggle` 的視覺）
  - free-form view：單一大 `<textarea>` 綁 `free_form_markdown`
  - structured view：6 個分節，每節一個 label + `<textarea>`
  - 底部固定「儲存」按鈕（`Save` zh-TW / `儲存`）；mutation pending 時 disabled + 顯示 `Saving…`
  - Mutation 完成後 toast 替代方案：在按鈕旁顯示 `已儲存 ✓`（淡出 2s）；錯誤改顯示 i18n 字串
- 沒切 view 不丟失未存檔內容：兩邊共用同一份 7-欄位 state；`free_form_markdown` 與其他 6 欄位完全獨立、不互相覆寫

### Embed PlaybookPane into the meeting detail page

- 檔案：`packages/web/src/routes/meetings/detail.tsx`
- 在 detail 卡片下方加入 `<PlaybookPane meetingId={id} />` 區塊（不另開 sub-route）
- 不影響 detail 頁原有刪除流；PlaybookPane 自帶 loading / error UI

### `lib/playbook-api.ts` query options + mutation hook

- 檔案：`packages/web/src/lib/playbook-api.ts`
- 公開：
  - `getPlaybook(meetingId): Promise<Playbook>`
  - `upsertPlaybook(meetingId, payload): Promise<Playbook>`
  - `playbookQueryOptions(meetingId)` → `{ queryKey: ["playbook", meetingId], queryFn: () => getPlaybook(meetingId) }`
  - `useUpsertPlaybookMutation(meetingId)` → `mutationFn: (payload) => upsertPlaybook(meetingId, payload)`；onSuccess invalidate `["playbook", meetingId]`
- 與 `meetings-api.ts` 共用 `MeetingApiError` 風格，但用 `PlaybookApiError`（同一基底） — 或共用 `ApiError` class；本 slice 內挑「共用 base class」以免重複

### Test strategy (TDD vertical slice)

- Backend（pytest + httpx async client + 真實 PostgreSQL test DB）：
  - `tests/playbooks/test_repository.py` — `get_or_create` 第一次建立、第二次直接拿；`upsert` 完整覆蓋；中英混用 markdown 內容（含標題 / 列表 / 60+ 行長文）
  - `tests/playbooks/test_endpoints.py` — GET 第一次自動建立、ownership 跨 user → 404；PUT full upsert；reload 後欄位仍在
  - `tests/playbooks/test_validation.py` — 缺欄視為空字串（非 422）；過長 markdown body（>10K 字元）能存能讀
- Frontend（bun test + happy-dom）：
  - `lib/playbook-api.queries.test.ts` — `playbookQueryOptions` 的 queryKey 與 queryFn 行為
  - `lib/playbook-api.mutations.test.tsx` — `useUpsertPlaybookMutation` 成功後 invalidate 正確 query key
  - `components/playbook-pane.test.tsx` — toggle 切視圖不丟內容；存檔送 PUT；錯誤訊息走 i18n
- 修改 `packages/backend/tests/conftest.py` 在 teardown 加入 TRUNCATE playbook（以免 slice-03 的 truncate 漏掉新表）

## Risks / Trade-offs

- [Risk] `get_or_create` 在 high-concurrency 下若兩個 GET 同時打到同一個未建立的 meeting playbook 可能爆 UNIQUE → Mitigation：用 `INSERT ... ON CONFLICT (meeting_id) DO NOTHING RETURNING *` 模式或改 `INSERT ... ON CONFLICT DO UPDATE SET id=id` 取回 row；單人桌面 app 場景幾乎不會發生，仍寫進實作以防萬一
- [Risk] 純 textarea 不支援 markdown highlight / preview，使用者體驗較陽春 → Mitigation：本 slice 把 v1 體驗訂明，未來若需要 wysiwyg 再開 refactor change（如 `@uiw/react-md-editor`）。Issue 也明文允許 textarea
- [Risk] PUT 採 full upsert，client 漏帶某欄會被覆寫成空字串 → Mitigation：前端 `PlaybookPane` 永遠把當前 7 欄位完整送出；schema 的 default `""` 只是後端 robustness；單元測試覆蓋「漏帶欄位 → 變空字串」與「完整 PUT」兩種情境
- [Trade-off] view 切換不丟失內容意味著兩邊永遠 in-sync — 結構化欄位與 free-form body 是獨立資料、不會互相轉譯（Slice 5 LLM 才會做雙向轉譯）

## Migration Plan

1. `alembic revision --autogenerate -m "create playbook table"` → 手動修整為上述 schema（autogen 對 UNIQUE 與 server_default 表現不一致）
2. `alembic upgrade head` 跑 dev DB；rollback 用 `alembic downgrade -1`（一步回到 0001_create_meeting）
3. 沒有資料遷移（本 slice 之前無 playbook 資料）
4. 前端 build 不需配置變更；不引入新依賴
5. 對 dev DB 跑一次 `alembic upgrade head` 後，slice-03 的所有 endpoint 仍能正常運作（playbook 表與 meeting 表互不干擾）

## Open Questions

- 「儲存後」UI 提示要不要做 toast？決議：本 slice 用按鈕旁的小字提示 `已儲存 ✓` 即可，toast 系統留待 Slice 8 統一處理
- structured 視圖六個欄位要不要支援拖曳排序？決議：否，固定順序 — objective → counterparty_profile → anticipated_topics → anticipated_objections → talking_points → red_lines
- 是否要把 free_form_markdown 與 6 結構化欄位 join 成一份 markdown 在 GET 回傳？決議：否，client 永遠拿到 7 個獨立欄位；Slice 5 LLM 會在生成時自己決定要不要做雙寫
