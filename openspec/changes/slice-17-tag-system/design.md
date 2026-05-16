## Context

Slice 17 解的是「會議多了沒辦法分類找」這個 UX 缺口。前面 16 個 slice 把 meeting lifecycle 全部接通（pre / in / post-meeting），但 meetings list / kanban / calendar 上只有 title + 時間 + 狀態三個分類維度，沒法快速「給我看所有跟客戶 X 的會議」或「所有面試類的會議」。

Slice 17 加一個 per-user 扁平 tag 系統。Schema 兩張表：`tag` 是 per-user namespace 的 tag definition，`meeting_tag` 是 N:M junction。`(user_id, lower(name))` unique 保證「客戶X」「客戶x」「客戶 X」之中三個寫法只能其一存在（case-insensitive）。Single user 專案，不做 sharing；preset 8–10 色 palette 避免使用者選一堆 dual-theme 對比度毀掉的「自由色」。

deep module 是 `TagRepository`，per Sean 全域偏好 + PRD 列入 TDD 清單，必須測試先行驗證：(a) per-user case-insensitive uniqueness、(b) hard delete cascade 到 junction、(c) attach 時 enforce ≤ 10 tags per meeting。

## Goals / Non-Goals

**Goals:**

- Per-user 扁平 tag CRUD + meeting attach/detach API。
- Meetings list / kanban / calendar 三個視圖都能顯示 `<TagChip>` + 用 `<TagFilter>` 多選 tag 做 AND 過濾。
- `/settings/tags` 管理頁能 rename / recolor / hard delete tag；hard delete 時動態顯示「將從 N 個會議移除」。
- `TagRepository` 走 TDD：case-insensitive uniqueness、cascade-on-delete、≤ 10 tags-per-meeting limit 全部 red-test 先寫。
- i18n 所有新字串 zh-TW + en 同步；CONTEXT.md glossary 加「Tag (標籤)」。
- 既有 `GET /api/meetings` 與 `GET /api/meetings/{id}` payload 加 `tags: [{id, name, color}]` array，不破壞既有 contract。

**Non-Goals:**

- Hierarchical / nested tags — 扁平結構，不做 parent-child。
- Auto-tagging by LLM — 不分析 transcript / playbook 內容自動掛 tag。
- Tag sharing across users — single-user 專案，tag 永遠 per-user scope；junction `meeting_id` 也是 per-user owned meeting。
- 完全自訂顏色 — preset palette only，避免低對比 / 與 dual-theme（紫羅蘭 / 暖橘）撞色。
- Tag analytics / usage stats — `/settings/tags` 不顯示「最常用」「最後使用」。
- Bulk attach / detach UI — 一次只能對單一 meeting attach / detach。
- Smart filters / saved views — `<TagFilter>` state 僅 session-level，不存 user preference。
- 修改既有 meeting 排序或 kanban bucketing — 過濾後仍走既有「newest-first by created_at」與 Today / Upcoming / Past bucket 邏輯。

## Decisions

### Schema：`tag` + `meeting_tag` 雙表，case-insensitive uniqueness 用 expression index

`tag` 表 columns：`id TEXT PRIMARY KEY`（用 cuid2 / nanoid，跟既有 meeting id pattern 一致）、`user_id TEXT NOT NULL` FK 到 Better Auth `user.id` ON DELETE CASCADE、`name TEXT NOT NULL`（≤ 50 chars，trim whitespace at write time）、`color TEXT NOT NULL`（hex string 從 preset palette 挑，server-side enum 驗證）、`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`。Unique constraint 用 expression index：`CREATE UNIQUE INDEX uq_tag_user_name ON tag (user_id, lower(name))` — 確保「客戶X」「客戶x」「客戶 X」中後兩個（trim 後）視為同名。**Alternative considered**：在 application layer 做 case-insensitive check —— 被否決，race condition 下會雙寫；DB 層 unique index 才是 source of truth。

`meeting_tag` 表 columns：`meeting_id TEXT NOT NULL` FK 到 `meeting.id` ON DELETE CASCADE、`tag_id TEXT NOT NULL` FK 到 `tag.id` ON DELETE CASCADE、`attached_at TIMESTAMPTZ NOT NULL DEFAULT now()`。複合主鍵 `(meeting_id, tag_id)`。雙向 cascade：刪 meeting → junction 跟著消失；刪 tag → 從所有 meeting 上自動移除。**Alternative considered**：soft delete（加 `deleted_at` column）—— 被否決，per Non-Goals 不要 analytics / 歷史保留，single user 也沒有「誤刪救援」的協作需求。

### Color palette：preset 8 色，存 hex string，前後端共用 enum

Palette 定義一處：`packages/web/src/lib/tag-palette.ts` export `TAG_PALETTE: readonly string[]` 共 8 色（紫 / 藍 / 青 / 綠 / 黃 / 橘 / 紅 / 灰），oklch 中度飽和、light + dark 兩 theme 都有可讀對比度（避開全飽和 → dark mode 太亮、避開太淺 → light mode 太弱）。Backend 同步保存一份白名單在 `packages/backend/meeting_playbook/tags/colors.py`，`POST/PATCH /api/tags` 驗 `color in TAG_PALETTE_HEX` 否則回 422 `tag.invalid_color`。**Alternative considered**：自訂顏色 picker —— 被否決，per Non-Goals。**Alternative considered**：preset 用 semantic name（"primary" / "warning"）而非 hex —— 被否決，前端要在 9 種不同 component（chip / picker / filter / kanban card / calendar pill / settings row / etc）都用同一顏色，hex 直接餵 `style={{ backgroundColor }}` 最簡。

### `<TagChip>` / `<TagPicker>` / `<TagFilter>` 三個元件分工

`<TagChip>`：display-only，props `{name, color, onRemove?, size?: 'sm'|'md'}`；用 oklch 變數計算對比文字色（亮色 chip 用深字、深色 chip 用亮字）。掛在 meeting card / kanban card / calendar event pill / detail page header / `<TagFilter>` 內。**沒有** API 呼叫；純展示。

`<TagPicker>`：popover trigger 顯示「+ 新增標籤」chip，opened state 展開 `<Command>`-based search input + 既有 tag list + 「建立『{query}』」inline create row（query 不在既有 tag 內時才出現）。Props `{meetingId, currentTags, onAttached, onDetached}`。Click 既有 tag → `POST /api/meetings/{id}/tags`；click create row → `POST /api/tags` then `POST /api/meetings/{id}/tags`（兩段呼叫，client 端先建 tag、拿到 id 再 attach）。已掛上的 tag 顯示打勾，click 變成 detach 走 `DELETE /api/meetings/{id}/tags/{tag_id}`。掛在 meeting detail page header + 也可考慮 meeting card hover state（slice 17 不做，列為 followup）。

`<TagFilter>`：multi-select dropdown trigger 顯示「標籤 (N)」counter；opened 展開所有 tags 加 checkbox。State 是 `tagIds: string[]`，存 URL search param `?tag_ids=a,b,c`（讓重新整理保留 filter；不存 localStorage、不存 server-side user preference per Non-Goals）。掛在 meetings list / kanban / calendar 上方共用列。**Alternative considered**：把 TagFilter 內聚進 MeetingsViewTabs —— 被否決，三視圖 view tab 切換時希望保留 filter state，所以 filter 是 wrapper 層，view tabs 是 child。

### `?tag_ids=` AND 過濾語意

`GET /api/meetings?tag_ids=t_a,t_b` 表示 **每個列出的 meeting 必須同時掛上 t_a 且 t_b**（AND，不是 OR）。理由：使用者 mental model「縮小範圍」比「擴大範圍」常見；OR semantics 容易誤觸（multi-select 順手點兩個變成「客戶 X 或 客戶 Y」反而擴大結果）。實作走 `WHERE meeting.id IN (SELECT meeting_id FROM meeting_tag WHERE tag_id = ANY(:ids) GROUP BY meeting_id HAVING COUNT(DISTINCT tag_id) = :n)`。空 `tag_ids` query param 等同沒傳，回所有 meetings。任一 tag_id 不存在 / 不屬於該 user → 回 422 `tag.unknown_id`（不沉默忽略，否則 typo 會以為 filter 沒效果）。**Alternative considered**：OR semantics 加額外 query `?match=or` —— 被否決，slice 17 不需要兩種 mode；加 query 是後續 enhancement 才做。

### 單一 meeting ≤ 10 tags：DB CHECK 還是 application enforce？

走 application enforce + `POST /api/meetings/{id}/tags` 在 transaction 內 `SELECT COUNT(*) FROM meeting_tag WHERE meeting_id = :id FOR UPDATE` 鎖該 meeting 的 junction rows、檢查 < 10、才插入；違反 → 回 422 `tag.too_many_for_meeting`，message 含當前 tag 數量。**Alternative considered**：DB-level CHECK constraint 用 trigger —— 被否決，PostgreSQL 沒有「count of junction rows」level 的 declarative constraint，需要 trigger；Repository 層 + `FOR UPDATE` lock 已能保證單 process 正確性，且測試 / 觀察錯誤訊息都比 trigger 容易。Single user race condition 風險極低（不會同時兩個 client 對同一 meeting attach）。

### Hard delete 確認文案「將從 N 個會議移除」

`/settings/tags` 列表每 row 有 delete icon；click 開 `AlertDialog`，標題「刪除標籤『{name}』？」、描述「此標籤目前掛在 N 個會議上，刪除後將從這些會議移除。此動作無法復原。」。**N 從哪來**：列表 query 一次回 `GET /api/tags?with_meeting_count=true` 拿 `meeting_count` 欄位（SQL `COUNT(*) FROM meeting_tag` GROUP BY tag_id），列表渲染時就有；delete 對話框直接讀 row data，不額外 round-trip。i18n key 用 `t("settings.tags.deleteConfirm", { count: N })` + ICU plural（en：「This tag is attached to {count, plural, one {1 meeting} other {# meetings}}」）。zh-TW 一律「N 個會議」（中文沒有單複數）。**Alternative considered**：刪除前再打一次 API count —— 被否決，列表 render 時已知 count，多一次 round-trip 沒意義。

### Repository 的 cascade 行為走 DB FK，不在 application 層手動 delete

`TagRepository.delete(tag_id, user_id)` 只 issue `DELETE FROM tag WHERE id = :tag_id AND user_id = :user_id`，依靠 FK ON DELETE CASCADE 把 `meeting_tag` 連帶清掉。**Alternative considered**：repository 先 delete junction、後 delete tag —— 被否決，DB 已能保證 atomic cascade，多一段 query 反而增加 race window。整合測試驗證：建 tag、attach 到 3 個 meeting、`repo.delete(tag_id)` 後 `meeting_tag` 0 rows、tag 0 rows。

### 既有 meeting payload 怎麼加 `tags` array：N+1 prevention

`GET /api/meetings` 是熱 path（首頁就是這個 endpoint），若每個 meeting 都單獨查 tags 就 N+1 死掉。實作走 single batch query：`MeetingRepository.list_for_user_with_tags(user_id, tag_id_filter=None)` 用 `selectinload(Meeting.tags)` 在一個 query 內預 join junction + tag 表。SQLAlchemy 2.0 async pattern 直接走 relationship + selectinload。**Alternative considered**：兩段 query，先 list meetings 拿 id list、再 `SELECT * FROM tag JOIN meeting_tag` —— 被否決，selectinload 是 SQLAlchemy 推薦做法且測試 fixture 比較好寫。

### `<TagFilter>` URL state：用 search param 不用 path

URL 形如 `/meetings?tag_ids=t_a,t_b&view=kanban`。Meetings list / kanban / calendar 同一個 layout container（per slice-11 archive）讀同一個 search param。空字串 / 缺 param 都視為「無 filter」回所有 meetings。**Alternative considered**：URL path 例如 `/meetings/tag/t_a` —— 被否決，AND 多選會讓 path 變奇形怪狀（`/meetings/tag/t_a+t_b`）且不能跟 `view=kanban` 並存。

## Implementation Contract

- **新 SQLAlchemy models `packages/backend/meeting_playbook/tags/models.py`**：
  - `Tag(id, user_id, name, color, created_at)` 對應 `tag` 表。
  - `MeetingTag(meeting_id, tag_id, attached_at)` 對應 `meeting_tag` 表。
  - `Meeting.tags: list[Tag]` relationship（many-to-many via `MeetingTag`）。
- **新 Alembic migration `XXXX_tag_system.py`**：建兩張表 + expression unique index + FK CASCADE；down 是 drop（先 drop junction 再 drop tag）。
- **新 `TagRepository`** at `packages/backend/meeting_playbook/tags/repository.py`：
  - `list_for_user(user_id, with_meeting_count=False) -> list[TagWithMeta]`。
  - `create(user_id, name, color) -> Tag`：trim name、檢查 `lower(name)` 唯一（依靠 DB unique index、catch IntegrityError 轉成 `TagNameTaken`）、驗 `color in PALETTE`（否則 `InvalidTagColor`）。
  - `update(user_id, tag_id, name?, color?) -> Tag`：同樣 uniqueness 檢查；`tag_id` 不屬於 user 視同 not found。
  - `delete(user_id, tag_id) -> None`：依靠 FK cascade 清 junction。
  - `attach(user_id, meeting_id, tag_id) -> MeetingTag`：在 transaction 內 lock meeting's junction rows、check < 10、insert；違反 raise `TagLimitExceeded(current_count)`；duplicate (meeting,tag) pair 視為 idempotent no-op 回現有 row。
  - `detach(user_id, meeting_id, tag_id) -> None`：delete junction row；不存在視為 no-op。
- **新 FastAPI router `packages/backend/meeting_playbook/tags/router.py`**：
  - `GET /api/tags?with_meeting_count=bool` → 200 `[{id, name, color, created_at, meeting_count?}]`。
  - `POST /api/tags` body `{name, color}` → 201 `{id, name, color, created_at}`；name 重複回 422 `tag.name_taken`；invalid color 回 422 `tag.invalid_color`。
  - `PATCH /api/tags/{tag_id}` body `{name?, color?}` → 200 同上；same error codes。
  - `DELETE /api/tags/{tag_id}` → 204。
  - `POST /api/meetings/{meeting_id}/tags` body `{tag_id}` → 201 `{meeting_id, tag_id, attached_at}`；超過 10 個回 422 `tag.too_many_for_meeting` message 含 `current_count`；tag 不屬於 user 回 404；meeting 不屬於 user 回 404。
  - `DELETE /api/meetings/{meeting_id}/tags/{tag_id}` → 204；不存在的 (meeting, tag) pair 仍回 204（idempotent）。
- **既有 `packages/backend/meeting_playbook/meetings/repository.py` 與 `router.py`** 擴：
  - `list_for_user(user_id, tag_ids: list[str] | None = None)` 簽名加 tag_ids 過濾參數，selectinload tags。
  - `get_for_user(user_id, meeting_id)` selectinload tags。
  - `GET /api/meetings` 接收 `?tag_ids=a,b,c`（comma-separated），解析後傳 repository；任一 id 不屬於該 user → 422 `tag.unknown_id`。
  - List + detail response payload 加 `tags: [{id, name, color}]`。
- **新前端 components 與 routes**：
  - `packages/web/src/components/tags/tag-chip.tsx` — display-only chip。
  - `packages/web/src/components/tags/tag-picker.tsx` — popover with Command search + inline create。
  - `packages/web/src/components/tags/tag-filter.tsx` — multi-select dropdown，state in URL search param。
  - `packages/web/src/routes/settings/tags.tsx` — 管理頁 list + create row + rename inline + recolor swatch + delete dialog。
  - `packages/web/src/route-tree.tsx` 加 `/settings/tags` route。
- **新 API client wrapper `packages/web/src/lib/tags-api.ts`**：包 `listTags / createTag / updateTag / deleteTag / attachTag / detachTag` 對應上述 endpoints；錯誤 throw `ApiError(error_code, message)` 讓 caller 走 `localizedErrorMessage`。
- **新 palette source `packages/web/src/lib/tag-palette.ts`**：export `TAG_PALETTE: readonly string[]` 與 helper `pickReadableTextColor(bg: string): 'light' | 'dark'`；backend 同步 `packages/backend/meeting_playbook/tags/colors.py` 維護同 8 色 hex 白名單。
- **既有 meetings 視圖整合**：
  - `packages/web/src/routes/meetings/list.tsx`、`kanban.tsx`、`calendar.tsx`、`detail.tsx` 各自 import `<TagChip>` 顯示 tags、 import `<TagFilter>` 放在頁首；list/kanban/calendar 三個 route 共用同一個 URL search param `?tag_ids=`。
  - Meeting detail header 加 `<TagPicker>`。
- **i18n keys** 新增於 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json`：
  - `tags.chip.removeAria`、`tags.picker.placeholder`、`tags.picker.create`、`tags.picker.noResults`、`tags.filter.label`、`tags.filter.empty`、`settings.tags.title`、`settings.tags.createButton`、`settings.tags.namePlaceholder`、`settings.tags.colorLabel`、`settings.tags.deleteConfirm.title`、`settings.tags.deleteConfirm.description`、`settings.tags.deleteConfirm.cancel`、`settings.tags.deleteConfirm.confirm`、`errors.tag.nameTaken`、`errors.tag.invalidColor`、`errors.tag.tooManyForMeeting`、`errors.tag.unknownId`。
- **`CONTEXT.md` glossary 加「Tag (標籤)」一條**（描述：per-user 自訂的扁平分類標籤，可掛到 meeting 上做 list / kanban / calendar 過濾；單一 meeting 最多 10 個）。

**Acceptance：** task list 跑完後 `bun --filter @meeting-playbook/web test` 與 `cd packages/backend && uv run pytest` 全綠；手動驗證 list / kanban / calendar 三視圖 TagChip + TagFilter 互動；`/settings/tags` CRUD 操作含 delete 確認；超過 10 tag 顯示本地化錯誤訊息。

**Scope boundary** — In scope：兩張新表 + 互動 API + 三個元件 + 一個 settings page + 既有 meetings payload 加 tags array + 既有 list endpoint 加 `?tag_ids=` 過濾 + i18n + CONTEXT.md glossary。Out of scope：bulk attach UI、auto-tag by LLM、tag analytics、saved view、tag sharing、自訂色、tag color 編輯時 ripple 重新計算文字色之外的進階 contrast 演算法。

## Risks / Trade-offs

- **`<TagFilter>` URL state 與 view tabs URL state 衝突** → URL param naming 已明確分開（`view=` vs `tag_ids=`），但要在 review 時確認 navigate 切換 view tabs 不會清掉 `tag_ids`。
- **`?tag_ids=` 用 comma split 對 cuid2 / nanoid 安全（id 不含 comma），但若未來 id format 改變要重新檢視** → 在 router 用單元測試確認 comma split 邏輯，並在 cuid2 / nanoid id 內 assert 不含 `,`。
- **`selectinload` 對於有 100+ meetings 的 user 仍會把 tag 資料載入** → slice 17 規模單一使用者最多幾百個 meetings；若未來 pagination 落實再 review。pagination 不在 slice 17 範圍。
- **8 色 palette 對色盲使用者** → 8 色已選色弱友善（避免純紅綠對比），但若日後有 a11y 回饋可在後續 ADR 補。
- **`tag.name_taken` 與 trim whitespace 互動**：repository create 前先 `name.strip()` 再寫 DB；UI 端也要在 submit 前 trim 否則回 422 時 user 看不出哪裡重複。
- **TagPicker inline create 兩段呼叫的 atomicity**：若先 `POST /api/tags` 成功、後 `POST /api/meetings/{id}/tags` 失敗，會留下「孤兒 tag」。可接受（user 可在 `/settings/tags` 刪除），但要 surface 第二段錯誤訊息。

## Migration Plan

- 新 Alembic migration `XXXX_tag_system.py`：建 `tag` + `meeting_tag` 表 + expression unique index + FK CASCADE；down 是 drop。
- Rollout：合 main、跑一週確認既有 meetings list / kanban / calendar 視圖在 `?tag_ids` 為空時行為與現在一致（regression baseline）。
- Rollback：drop two tables；既有 meetings 不受影響（沒有 backfill 過 tag）。

## Open Questions

- 8 色 palette 具體 hex 值由 design step 決定 — 暫定參考 Tailwind 預設 200/400/600 色階對 oklch 三個 brightness 做 mapping，最終值在 apply 階段確認且通過 light + dark mode 視覺檢查。
- `<TagPicker>` 在 meeting card hover 時是否要快捷打開：slice 17 不做（detail page 已有 picker），但若使用體感不夠快可列 v1.2 followup。
- ICU plural 套件選擇：既有 i18next 已內建 plural support，沿用不引入新依賴。
