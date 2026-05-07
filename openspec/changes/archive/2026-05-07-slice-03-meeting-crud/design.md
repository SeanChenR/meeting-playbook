## Context

Slice 1（auth shell）已交付 Bun.serve gateway + `X-User-Id` header injection；Slice 2 已交付 i18n（zh-TW 預設、en 副選）。Backend 目前僅有 `GET /api/me`，沒有任何業務 table。本 slice 是後續所有 vertical slice（playbook / transcript / audio / advisor / summary）的前置條件——它們都會 FK 到 `meeting.id`，因此 Meeting CRUD 是 deep-module 的根節點。

依 ADR-0012、ADR-0021、ADR-0025：PostgreSQL 由 Alembic 管理應用表、Better Auth CLI 管理 auth 表；FastAPI 不自行驗證 session，僅信任 gateway 注入的 `X-User-Id`；TS 端不引入任何 ORM。

依 ADR-0016：speaker label 在資料層為 binary（counterparty / me），但顯示名稱由 meeting 自帶兩欄 free text。本 slice 為這兩欄 schema + UI 落地。

## Goals / Non-Goals

**Goals:**

- 一個可被後續 slice 共用的 `MeetingRepository`（async SQLAlchemy 2.0），並由它擔任 meeting 的唯一存取路徑。
- REST endpoints 完整四件套（POST/GET list/GET id/DELETE），所有授權邏輯一律以 `X-User-Id` 為主體，他人資料一律 404（不洩漏存在）。
- React 三頁（list / new / detail+delete），含空狀態、刪除確認對話框、結構化 error_code → i18n 對應。
- TDD 紅綠重構驗證 user isolation、required-field validation、status 預設、calendar_event_id 預設 null、ASR provider 預設 whisper。

**Non-Goals:**

- PATCH `/api/meetings/{id}`（編輯）。
- Status transition `scheduled → in_progress → completed`（Slice 6）。
- Calendar event 連結填值（Slice 5）。
- 列表分頁、搜尋、過濾、批次操作。
- 任何子實體（playbook / transcript / audio）的 schema 與 FK；本 slice 僅建立 Meeting 自身。

## Decisions

### Alembic migration: meeting table schema

- 檔案：`packages/backend/alembic/versions/<rev>_create_meeting.py`
- 欄位：
  - `id` TEXT PRIMARY KEY（產生方式：`secrets.token_urlsafe(16)`，與 Better Auth 的 user.id 同樣是字串型，避免 join 時型別不一致）
  - `user_id` TEXT NOT NULL，FK → `user.id` ON DELETE CASCADE
  - `title` TEXT NOT NULL
  - `counterparty_display_name` TEXT NOT NULL
  - `me_display_name` TEXT NOT NULL
  - `status` TEXT NOT NULL DEFAULT `'scheduled'`，CHECK IN (`scheduled`, `in_progress`, `completed`)
  - `asr_provider` TEXT NOT NULL DEFAULT `'whisper'`
  - `calendar_event_id` TEXT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`
  - `started_at` TIMESTAMPTZ NULL
  - `ended_at` TIMESTAMPTZ NULL
- Index：`(user_id, created_at DESC)` 支援 list page 主查詢；`id` PK 已自動建。
- 為什麼用 TEXT 而非 UUID：Better Auth 已產出字串 id（cuid/nanoid 風），FK 端跟著走最一致；對效能影響可忽略。
- 為什麼不直接 ENUM type：Alembic 對 PG enum 的 alter 體驗差，後續 slice 還要加值（例如 `cancelled`），用 CHECK constraint + TEXT 比較好遷移。
- 不偏離 ADR-0012 / ADR-0021 / ADR-0025。

### MeetingRepository (SQLAlchemy 2.0 async) as the single access path

- 檔案：`packages/backend/meeting_playbook/meetings/{models,repository,schemas}.py`
- `models.Meeting`: `MappedAsDataclass` + `Mapped[...]` typed columns。
- `repository.MeetingRepository`：建構子吃 `AsyncSession`；公開 method：
  - `async create(*, user_id: str, title: str, counterparty_display_name: str, me_display_name: str, asr_provider: str = "whisper") -> Meeting`
  - `async list_by_user(user_id: str) -> list[Meeting]`（依 created_at desc）
  - `async get_for_user(user_id: str, meeting_id: str) -> Meeting | None`（找不到或 owner 不同 → 一律回 None）
  - `async delete_for_user(user_id: str, meeting_id: str) -> bool`（true=刪到、false=找不到/不屬於該 user）
- 後續 slice 全部走這個 repo，不直接 query meeting table；這是 deep-module 的關鍵約束。

### FastAPI router with X-User-Id-based authorization

- 檔案：`packages/backend/meeting_playbook/meetings/router.py`，`server.py` mount `prefix="/api/meetings"`。
- 共用 dependency：`get_user_id(x_user_id: Annotated[str | None, Header(alias="X-User-Id")]) -> str`；缺 header → 回現行的 `gateway_required` error_code（與 slice-01 一致）。
- Pydantic schemas（`schemas.py`）：
  - `MeetingCreate(title: str, counterparty_display_name: str, me_display_name: str)`，三欄都加 `Field(min_length=1)` 並在 validator 中 strip 後再次檢查空字串。
  - `MeetingRead(id, user_id, title, counterparty_display_name, me_display_name, status, asr_provider, calendar_event_id, created_at, started_at, ended_at)`。
- Endpoints：
  - `POST /api/meetings` → 201 + `MeetingRead`；validation 失敗回 422，body 含 `error_code` 形如 `meeting.title.required` / `meeting.counterparty_display_name.required` / `meeting.me_display_name.required`。
  - `GET /api/meetings` → 200 + `list[MeetingRead]`（newest first）；空陣列也回 200。
  - `GET /api/meetings/{id}` → 200 / 404；404 body 不洩漏存在。
  - `DELETE /api/meetings/{id}` → 204 / 404。

### React routes and components

- 檔案：
  - `packages/web/src/routes/meetings/list.tsx` — `MeetingsList`：fetch + 排序由後端決定；空狀態提示「尚無 meeting，按下『+ 新會議』建立第一筆」/「No meetings yet…」。
  - `packages/web/src/routes/meetings/new.tsx` — `NewMeetingForm`：title / counterparty / me 三欄必填，client-side 先擋；submit 後 redirect 到 `/meetings/:id`。
  - `packages/web/src/routes/meetings/detail.tsx` — `MeetingDetail`：顯示 title、雙顯示名稱、status、timestamps；刪除按鈕觸發 shadcn `AlertDialog` 確認；確認後 DELETE 回 list。
- `App.tsx` 新增三條 route；登入後預設 redirect 由 `/home` 改為 `/meetings`（`/home` 仍可瀏覽）。
- `packages/web/src/lib/meetings-api.ts`：包 `fetch` 含相對路徑 `/api/meetings`，由 Vite proxy 與 Bun gateway 自動帶 cookie。錯誤統一拋 `MeetingApiError({ status, errorCode })`，UI 用 `t(errorCode)` 轉字串。
- i18n key：`meetings.list.empty`、`meetings.new.title_label` 等放在 `meetings.*` namespace；`zh-TW.json` 與 `en.json` 同步加入。

### Test strategy (TDD vertical slice)

- Backend（pytest + httpx async client + 真實 PostgreSQL test DB）：
  - `tests/meetings/test_repository.py` — repository CRUD（含 list 排序、`get_for_user` 跨 user 回 None）。
  - `tests/meetings/test_endpoints.py` — endpoints + user isolation（user A 看不到 user B 的 meeting；DELETE 跨 user 回 404）。
  - `tests/meetings/test_validation.py` — 缺欄/空字串 → 422 + 預期 error_code。
- Frontend（bun test + happy-dom + msw 或手 stub fetch）：
  - `routes/meetings/list.test.tsx` — empty / populated 兩種狀態。
  - `routes/meetings/new.test.tsx` — 必填驗證、submit 成功 redirect。
  - `routes/meetings/detail.test.tsx` — 渲染欄位、AlertDialog 確認流、DELETE 成功回 list。
- 不寫 e2e Playwright（Slice 1 只有 unit + integration round-trip 模式，沿用即可）；以 backend integration test 充當「端到端」覆蓋。

## Risks / Trade-offs

- **TEXT id vs UUID**: TEXT id 易讀但 join cost 比 UUID 略高 → 對單機 personal tool 規模可忽略；換 UUID 將與 Better Auth schema 不一致，成本更高。
- **404 vs 403 一律隱藏存在**: 純粹隱私決定；trade-off 是 audit log 看起來「好像 user 一直找不到資料」→ 用 structlog 在 server 端記錄真實原因（meeting 不存在 vs owner mismatch），response 仍對外統一 404。
- **CHECK constraint 而非 PG ENUM**: 加值不必 alter type，trade-off 是缺少資料庫層 enum metadata；以 SQLAlchemy `Literal` 型別 + Pydantic `Literal` 雙重把關。
- **No PATCH this slice**: 使用者打錯字得刪掉重建；範圍封住可降低本 slice 體積，未來 Slice 6 / 後續可加。
- **Default redirect 從 `/home` 改 `/meetings`**: 對既有登入流的小行為改變，需在 frontend 測試覆蓋；好處是首次點進來就看到 list page。

## Migration Plan

1. `alembic revision --autogenerate -m "create meeting table"` → 手動修整為上述 schema（autogen 對 CHECK / index 表現不一致）。
2. `alembic upgrade head` 跑 dev DB；rollback 用 `alembic downgrade -1` 一次拔掉 table。
3. 沒有資料遷移（本 slice 之前無 meeting 資料）。
4. 前端 build 不需配置變更；既有 monorepo 啟動指令已涵蓋。

## Open Questions

- 是否預先把 `started_at` / `ended_at` schema 寫進來？決定：是。雖然本 slice 不寫入，但 schema 預先佔位可省去未來 alter；read schema 也回出（皆為 null）。
- 是否需要 soft delete？決定：否。Issue 明文是 hard delete，且 cascade 在 schema 上設好（FK ON DELETE CASCADE 由本 slice 提供，後續子表跟著加）。
- ASR provider 預設值是 `whisper` 還是 `faster-whisper`？決定：`whisper` 字串為 logical name，後續 slice 在 ASR provider registry 端做映射；本 slice 不關心其實際指向哪個 implementation。
