## 1. Schema 與 migration

- [x] 1.1 [AC-1] 撰寫 `Alembic migration: meeting table schema` test：寫 `tests/test_alembic_meeting.py`，跑 upgrade 後驗證 `meeting` 欄位、CHECK constraint、`(user_id, created_at DESC)` index、FK ON DELETE CASCADE 都存在（紅）。
- [x] 1.2 [AC-1] 新增 `packages/backend/alembic/versions/<rev>_create_meeting.py`，落實 `Alembic migration: meeting table schema`（綠）。執行 `alembic upgrade head` / `downgrade -1` 確認可逆。

## 2. MeetingRepository（SQLAlchemy 2.0 async）

- [x] 2.1 [AC-1][AC-10] 撰寫 `MeetingRepository (SQLAlchemy 2.0 async) as the single access path` 測試：`tests/meetings/test_repository.py` 涵蓋 `Meeting belongs to exactly one user with strict ownership isolation`（user A 看不到 user B 的 meeting）與 `Meeting list is sorted newest-first by creation time`（紅）。
- [x] 2.2 [AC-1][AC-10] 在 `packages/backend/meeting_playbook/meetings/{models,repository}.py` 實作 `MeetingRepository`（create / list_by_user / get_for_user / delete_for_user），讓 2.1 測試轉綠。
- [x] 2.3 [AC-3] [P] 在 repository test 補 `Meeting status defaults to scheduled at creation` 與 `Meeting carries an optional Calendar event reference` 預設行為的單元測試（status='scheduled'、calendar_event_id=None）。
- [x] 2.4 [AC-1] [P] 在 repository test 補 `Meeting carries an ASR provider preference defaulting to whisper` 的測試（未指定時持久化為 `whisper`）。

## 3. FastAPI endpoints + 授權

- [x] 3.1 [AC-2][AC-3] 撰寫 `FastAPI router with X-User-Id-based authorization` endpoint test：`tests/meetings/test_endpoints.py` 涵蓋 POST/GET list/GET id/DELETE 四件套；驗證 `Meeting belongs to exactly one user with strict ownership isolation`（user A 取/刪 user B 的 meeting → 404，回應 body 不洩漏存在）（紅）。
- [x] 3.2 [AC-2][AC-3] 實作 `packages/backend/meeting_playbook/meetings/{router,schemas}.py` 與 `server.py` mount router，讓 3.1 測試轉綠。
- [x] 3.3 [AC-4] 撰寫 `Meeting carries a title, counterparty display name, and me display name` 的 validation test：`tests/meetings/test_validation.py` 缺欄/空字串 → 422 + `error_code` 形如 `meeting.title.required`（紅）。
- [x] 3.4 [AC-4] 在 schemas + router 加上 strip + min_length 與 error_code 對應，讓 3.3 測試轉綠。
- [x] 3.5 [AC-3][AC-7] [P] 補 endpoint test：`Meeting status defaults to scheduled at creation`（client 帶 status=completed 仍存為 scheduled）、`Meeting carries an optional Calendar event reference`（new meeting 回 calendar_event_id=null）、`Meeting carries an ASR provider preference defaulting to whisper`（GET 回 whisper）。

## 4. Frontend：list page

- [x] 4.1 [AC-5] 撰寫 `React routes and components` 之 list page test：`packages/web/src/routes/meetings/list.test.tsx` 涵蓋空狀態與已填入狀態，後者驗證 `Meeting list is sorted newest-first by creation time`（紅）。
- [x] 4.2 [AC-5][AC-9] 實作 `routes/meetings/list.tsx` + `lib/meetings-api.ts` + `App.tsx` 新增 `/meetings` route 與登入後 redirect；i18n key `meetings.list.empty` 等同步加進 `zh-TW.json` / `en.json`，讓 4.1 測試轉綠。

## 5. Frontend：new meeting form

- [x] 5.1 [AC-4][AC-6] 撰寫 new form test：`routes/meetings/new.test.tsx` 涵蓋必填欄位驗證、submit 成功 redirect 至 `/meetings/:id`（紅）。
- [x] 5.2 [AC-4][AC-6][AC-9] 實作 `routes/meetings/new.tsx`，串接 `MeetingApiError.errorCode → t(errorCode)`；i18n key 同步雙語，讓 5.1 測試轉綠。

## 6. Frontend：detail + delete

- [x] 6.1 [AC-7][AC-8] 撰寫 detail/delete test：`routes/meetings/detail.test.tsx` 驗證渲染欄位（title、counterparty / me 顯示名稱、status、timestamps）以及 AlertDialog 確認後 DELETE 回 list（紅）。
- [x] 6.2 [AC-7][AC-8][AC-9] 實作 `routes/meetings/detail.tsx`（含 shadcn AlertDialog）與 `App.tsx` 加 `/meetings/:id` route；i18n key 同步雙語，讓 6.1 測試轉綠。

## 7. End-to-end 整合 + 文件

- [x] 7.1 [AC-10][AC-11] 撰寫 `Test strategy (TDD vertical slice)` 收尾用的 backend integration test：模擬 gateway 注入 `X-User-Id` 完整跑一次 create → list → get → delete，覆蓋率達標（≥80%）。
- [x] 7.2 [AC-9] [P] 校對 `packages/web/src/i18n/locales/{zh-TW,en}.json`，確認所有新 `meetings.*` key 雙語齊備、無孤兒 key、無重複 key；以 unit test 或 lint script 守住。
- [x] 7.3 更新 `README.md` 或新增 `docs/agents/meetings.md` 短篇，說明 Meeting CRUD 端到端流程與 `MeetingRepository` 為唯一存取路徑的不可繞過原則。
- [x] 7.4 Verify all acceptance criteria from the agent brief are checked off in GitHub Issue #5.
