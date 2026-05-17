## Context

S20 之前的 meeting 各自獨立。實務上同一家客戶會持續開好幾場、internal alignment 與 customer call 也常成對出現，使用者只能憑記憶或 meetings list 翻找關聯會議。S21 引入手動 `related` 連結，讓使用者在 detail header 一眼看見「這場跟哪些其他會議有關」，並一鍵跳轉。

技術上的核心難點是 **bidirectional 語意**：DB 物理上只寫一條 row（`from_meeting_id → to_meeting_id`），但邏輯上「從 A 看 B」與「從 B 看 A」要對等。Repository 必須吃下這層抽象，讓 router 不關心 row 方向。`MeetingLinkRepository` 因此被列為 deep module，走 TDD：先寫「一邊建、另一邊查得到」的紅燈，再 green。

UI 端把 link 列表嵌進既有 `MetadataCard` header，重用 slice-meetings-ux-revamp 落地的 prev/next nav 排版風格，不另開一個 pane。

## Goals / Non-Goals

**Goals:**

- 使用者可在 meeting detail header 看到該會議所有 related links，點擊跳轉。
- 寫一條 row、從兩端任一邊都查得到（bidirectional）。
- 同對 meeting 不論順序、不論誰先發 POST，第二次發必被 reject（409，含 `error_code = "meeting_link.duplicate"`）。
- 任一端發 DELETE 都能刪掉那條 link（不需區分「誰是 from」）。
- 完全可選 —— 使用者沒建 link，detail header 顯示「尚無關聯會議」空狀態，不阻擋任何既有流程。
- 對既有 `meeting-detail-layout` 規範向下相容：新元素加在 header 群組裡，prev/next nav、BackLink、狀態 badge 行為 0 改動。

**Non-Goals:**

- LLM 自動推薦 related meetings（v1.2 backlog）。
- `link_type` 多語意（v1.1 凍結為 `"related"`；schema 留欄位佔位）。
- Bulk multi-select picker、cross-user share、calendar series 自動連結（皆超出 S21）。
- 在 meetings list / calendar / Kanban 視圖顯示 link 數量（v1.1 只在 detail header 顯示）。
- 修改 Better Auth tables 或 user FK 語意。

## Decisions

### Schema：單向 row + bidirectional Repository 抽象

`meeting_link` 在 DB 物理上只存一條 row `(id, from_meeting_id, to_meeting_id, link_type, created_at)`，`link_type` 預設值 `'related'`、`NOT NULL`、`CHECK (link_type IN ('related'))`，留下未來加 `'follow_up'` / `'prep_for'` 的擴充欄位但不在 v1.1 開放。Bidirectional 語意（兩邊都查得到）放在 Repository 層，用 `WHERE from_meeting_id = :id OR to_meeting_id = :id` 一條 SQL 查所有相關 link。**Alternative considered**：每次建立 link 就寫兩條 row（A→B 與 B→A）—— 被否決，重複資料造成「`(A, B)` 與 `(B, A)` 算同一條還是兩條？」歧義，且 DELETE 要刪兩 row 才能保持一致，反而提高複雜度。

### 同對 meeting 去重：partial unique index on `LEAST/GREATEST`

PostgreSQL `CREATE UNIQUE INDEX meeting_link_pair_uidx ON meeting_link (LEAST(from_meeting_id, to_meeting_id), GREATEST(from_meeting_id, to_meeting_id))`。這讓「A→B」與「B→A」在索引層映射到同一個 key，第二次 insert 觸發 `UniqueViolation`，repository 捕捉後轉成 `MeetingLinkDuplicate` domain exception，router 回 HTTP 409 + `error_code = "meeting_link.duplicate"`。**Alternative considered**：在 application 層先 SELECT 再 INSERT —— 被否決，TOCTOU race condition，雙 click 會建出兩條重複 row；DB-level 約束是唯一正確的去重保證。**Alternative considered**：在 row 寫入前 normalize 成 `(min_id, max_id)` —— 被否決，會把「誰先建立 link」這個次要語意（記在 `from_meeting_id`）也抹掉，且未來 v1.2 加 directional `link_type`（如 `prep_for`）時，from/to 方向就有意義了，現在 normalize 反而要再 migration 一次。

### Ownership 驗證：兩端 meeting 都必須屬於 current user

每個 endpoint（GET / POST / DELETE）先把 `X-User-Id` header 對到 `meeting.user_id`，POST 需驗 `from_meeting_id` 與 `to_meeting_id` 兩個 meeting 都屬於同一 user，不屬於則回 HTTP 404（不洩漏「該 meeting 存在於他人帳號下」）。DELETE 路徑同理：先查 link → 確認其中至少一端 meeting 屬於 current user → 才允許刪除。**Alternative considered**：在 DB 加 trigger 強制 `meeting.user_id` 一致 —— 被否決，application 層驗證已足且更可讀；trigger 拉長 migration 複雜度且難 test。

### `MeetingLinkRepository` 介面（deep module）

只暴露四個方法，所有 bidirectional 細節由內部處理：

- `list_for_meeting(meeting_id: UUID) -> list[MeetingLinkView]`：回 `[{link_id, other_meeting_id, other_meeting_title, other_meeting_scheduled_start_at, link_type, created_at}, ...]`，永遠以 `other_meeting` 視角呈現（呼叫端不需要知道 from/to 方向）。
- `create(from_meeting_id: UUID, to_meeting_id: UUID, link_type: str = "related") -> MeetingLink`：呼叫端傳兩個 meeting id，repository 內部以 `from < to` 為慣例（minor convention）寫入但不依賴此慣例做查詢；違反 unique constraint → raise `MeetingLinkDuplicate`；`from == to` raise `MeetingLinkSelfReference`。
- `delete(link_id: UUID) -> bool`：依 link_id 刪，回是否刪到（0 row 回 False，1 row 回 True）。
- `get(link_id: UUID) -> MeetingLink | None`：給 DELETE endpoint 在驗 ownership 前取 link 兩端 meeting_id。

**Alternative considered**：把 `list_for_meeting` 拆成 `list_outgoing` + `list_incoming` —— 被否決，這是「shallow module」反模式：呼叫端被迫關心 from/to 方向，正是這層抽象要消除的細節。**Alternative considered**：回 `list[MeetingLink]` 不做 join —— 被否決，前端列表顯示需要 other meeting 的 title / scheduled time，N+1 query 會在 detail page render 時顯著拖慢；一次 join 拿齊。

### Bidirectional query 實作 SQL

```sql
SELECT
  ml.id AS link_id,
  CASE WHEN ml.from_meeting_id = :id THEN ml.to_meeting_id ELSE ml.from_meeting_id END AS other_meeting_id,
  m.title AS other_meeting_title,
  m.scheduled_start_at AS other_meeting_scheduled_start_at,
  ml.link_type,
  ml.created_at
FROM meeting_link ml
JOIN meeting m
  ON m.id = CASE WHEN ml.from_meeting_id = :id THEN ml.to_meeting_id ELSE ml.from_meeting_id END
WHERE ml.from_meeting_id = :id OR ml.to_meeting_id = :id
ORDER BY ml.created_at DESC;
```

對 `meeting_link.from_meeting_id` 與 `meeting_link.to_meeting_id` 個別建 index 支援 `OR` 查詢；`meeting.id` 是 PK，join 走 PK index。

### API 路由設計：mount 在 meeting 下

`GET / POST` 走 `/api/meetings/{id}/links`（`id` 是「以哪個 meeting 為觀察點」），DELETE 走 `/api/meetings/{id}/links/{link_id}`，路徑上的 `id` 用來做 ownership double-check（必須是該 user 的 meeting），實際被刪的 row 由 `link_id` 決定。**Alternative considered**：用 flat `/api/meeting_links/{link_id}` —— 被否決，無法靠 URL 表達「從哪個 meeting 視角操作」，且 GET list 要 query param `?meeting_id=X` 不夠 RESTful。

### `<MeetingLinkPicker>` typeahead：用 React Query 抓既有 meeting list

picker 開啟時不額外打 API，重用既有 `meetingsListQueryOptions()` 從 React Query cache 拿（cache 來自 meetings list / kanban / calendar 路徑）。client-side 篩：(a) 排除當前 meeting；(b) 排除已連結 meeting（從 `useQuery` `meetingLinksQueryOptions(meetingId)` 拿 link 列表後比對）；(c) typeahead 走 substring match on title（case-insensitive）。**Alternative considered**：在 backend 加 `GET /api/meetings?exclude_linked_to={id}&q={query}` —— 被否決，server-side 過濾需要連表，且 typeahead UX 對 latency 敏感，client-side filter 配既有 cache 體驗最好。Cache miss（使用者直接 deep-link 進 detail）的回退：picker 顯示「請先到會議列表載入會議清單」提示 + 入口連結。

### i18n：新增 `meetings.links.*` 命名空間

兩 locale 同步新增：

- `meetings.links.heading` — 「關聯會議」 / 「Related meetings」
- `meetings.links.count_one` / `count_other` — i18next plural
- `meetings.links.empty` — 「尚無關聯會議」 / 「No related meetings yet」
- `meetings.links.addButton` — 「+ 關聯」 / 「+ Link」
- `meetings.links.picker.placeholder` — typeahead 搜尋提示
- `meetings.links.picker.cacheMiss` — cache miss 回退文案
- `errors.meeting_link.duplicate` / `errors.meeting_link.self_reference` / `errors.meeting_link.not_found`

`localizedErrorMessage` 自動處理回退（不在 locale 的 code 回 `errors.common.unknown`），與既有 `i18n-errors.ts` 行為一致。

## Implementation Contract

- **新 schema `meeting_link`**（in scope）：columns `(id UUID PK default gen_random_uuid(), from_meeting_id UUID NOT NULL REFERENCES meeting(id) ON DELETE CASCADE, to_meeting_id UUID NOT NULL REFERENCES meeting(id) ON DELETE CASCADE, link_type TEXT NOT NULL DEFAULT 'related' CHECK (link_type IN ('related')), created_at TIMESTAMPTZ NOT NULL DEFAULT now())`，加 `CHECK (from_meeting_id <> to_meeting_id)` 防自連，加上述 `LEAST/GREATEST` partial unique index 與 from/to 個別 index。Alembic up 建表 + index + check + FK；down drop table（FK CASCADE 會帶走 row，不需手動清）。
- **新模組 `packages/backend/meeting_playbook/meeting_links/`** 暴露：
  - `MeetingLink` SQLAlchemy model（對應上述 schema）。
  - `MeetingLinkView` Pydantic schema（list endpoint 用的 join 後結構）。
  - `MeetingLinkRepository` 暴露上面四個方法；duplicate 走 `MeetingLinkDuplicate` exception、self-reference 走 `MeetingLinkSelfReference` exception。
  - `meeting_links_router`（FastAPI APIRouter mount 在 `/api/meetings/{id}/links`）：三條 endpoint 行為見下。
- **API 行為**（in scope）：
  - `GET /api/meetings/{id}/links` — 200 + `{"links": [MeetingLinkView, ...]}`；`id` 不屬於 current user → 404 `meeting.not_found`。
  - `POST /api/meetings/{id}/links` body `{"to_meeting_id": UUID}` — 201 + `{"link_id": UUID}`；`to_meeting_id == id` → 422 `meeting_link.self_reference`；duplicate（任一方向）→ 409 `meeting_link.duplicate`；任一端 meeting 不屬於 user → 404 `meeting.not_found`。
  - `DELETE /api/meetings/{id}/links/{link_id}` — 204；link 不存在 / 兩端皆非 user 的 meeting → 404 `meeting_link.not_found`。
  - 所有錯誤 response shape 沿用既有 `{error_code, message}` 慣例，可被 `localizedErrorMessage` 解析。
- **前端**（in scope）：
  - `<MeetingLinksSection meetingId={...}>` 渲染在 `MetadataCard` header（既有 prev/next nav 群組之後、metadata 兩欄之前）：顯示 heading + count + 展開的 link list + 「+ 關聯」按鈕；空狀態顯示 `meetings.links.empty`；clicking 「+ 關聯」開 `<MeetingLinkPicker>` modal；clicking 既有 link 跳轉 `/meetings/{other_meeting_id}`；每個 link 旁邊有刪除 icon（垃圾桶）—— 點擊發 DELETE。
  - `<MeetingLinkPicker>` Modal：typeahead 輸入、即時顯示過濾結果 list（排除當前 meeting + 已連結 meeting）；選 + 確認 → 發 POST、成功 invalidate `meetingLinksQueryOptions(meetingId)`；失敗顯示對應 i18n 錯誤訊息（不關閉 modal，讓使用者可重試或改選）。
  - `meeting-links-api.ts` 包三個 API helper（list / create / delete），使用 fetch + `X-User-Id` 透傳由 gateway 處理。
  - 兩 locale 同步新增 `meetings.links.*` 命名空間與 `errors.meeting_link.*` 三條錯誤；`locales.test.ts` deep-equal 通過。
- **CONTEXT.md glossary** 加「Meeting link」一條（描述：使用者手動建立的 `related` 連結；bidirectional 語意）。

**Failure modes**:

- Duplicate POST → 409 + `error_code = "meeting_link.duplicate"`；frontend modal 內顯示「這兩個會議已經連結了」/ "These meetings are already linked"，modal 不關閉。
- Self-reference POST → 422 + `error_code = "meeting_link.self_reference"`；frontend modal 內顯示「不能連結自己」/ "Cannot link a meeting to itself"。
- DELETE 不存在的 link → 204（idempotent，與 HTTP 規範一致）；或 404 若需要 client 區分。本 slice 採 **404** 比較有 debug 價值；frontend 把 404 視為「已被別處刪掉」，照常 invalidate cache。
- Meeting 被刪 → FK CASCADE 自動清掉所有相關 link rows，前端 React Query 重新 fetch 後 link 列表自動更新。

**Acceptance criteria**:

- Repository tests：red-then-green 涵蓋 (a) 寫 A→B 後 list_for_meeting(A) 與 list_for_meeting(B) 都回該 row 但對方視角的 `other_meeting_id` 對等；(b) 重複建立 (A,B) 或反向 (B,A) 都觸發 `MeetingLinkDuplicate`；(c) `create(A, A)` 觸發 `MeetingLinkSelfReference`；(d) `delete(link_id)` 回 True 後再 list 為空、二次 delete 回 False。
- Router tests：GET / POST / DELETE 三條 endpoint 含 ownership 隔離（不同 user 拿不到對方 link）、409 / 422 / 404 路徑全覆蓋。
- Frontend component tests：(a) 空狀態渲染；(b) 有 link 時顯示列表 + count；(c) 點 「+ 關聯」開 picker、選一筆後成功 POST + 列表 refresh；(d) 點刪除 icon 後 DELETE + 列表 refresh；(e) 422 self-reference 在 modal 內顯示本地化錯誤；(f) 409 duplicate 在 modal 內顯示本地化錯誤；(g) cache miss 時 picker 顯示「請先到會議列表」提示。

**Scope boundary** — In scope：`meeting_link` schema + Alembic migration、`MeetingLinkRepository` + `MeetingLinkView` + exception types、三條 REST endpoint、`<MeetingLinksSection>` + `<MeetingLinkPicker>` 元件、API helper、雙 locale i18n、CONTEXT.md glossary 一行。Out of scope：LLM 自動推薦、`link_type` 多語意、meetings list / calendar / kanban 顯示 link 數量、bulk picker、cross-user share、`/api/meetings?exclude_linked_to=` 等 server-side typeahead 端點。

## Risks / Trade-offs

- **`OR` query 沒走 index 時表現差** → 對 `from_meeting_id` 與 `to_meeting_id` 各建 B-tree index；PostgreSQL planner 在 `OR` 條件下會用 BitmapOr 合併兩個 index scan，個人使用量級下 latency 可忽略。Migration 內驗證 `EXPLAIN` 結果不走 seq scan。
- **`LEAST/GREATEST` unique index 在 PostgreSQL 12+** 才支援 expression index 上的特定 operator 推導 —— 專案目標 PG 15+，此風險不適用；但要在 migration 寫 comment 標出依賴。
- **DELETE 路徑 `link_id` 屬於不同 user 的 meeting** → ownership 檢查走 `get(link_id)` 後驗 `meeting.user_id == current_user`，至少一端通過才允許；測試需顯式涵蓋「user A 拿 user B 的 link_id 發 DELETE」回 404 case。
- **Cache miss UX** → 使用者 deep-link 進 detail 時 picker 拿不到 meetings list，回退顯示提示 + 連到 meetings list 的 link；首次體驗略差但屬罕見情境。**Mitigation**：在 detail page mount 時若 cache miss 可選擇性 trigger 一次 background prefetch；本 slice 不做，留 follow-up。
- **link 數量無上限**：理論上一個 meeting 可以連到所有其他 meeting；UI list render 在 50+ 時可能顯眼。**Mitigation**：v1.1 不設上限但 UI 在 > 10 條時自動 collapse 顯示「展開更多」；本 slice tasks 涵蓋此行為。

## Migration Plan

- Alembic migration 命名 `XXXX_meeting_link.py`：up 建表 + 兩個 secondary index + partial unique index + check constraint + FK CASCADE；down 是 drop table（CASCADE 不需手動清 rows）。Up / down / up 三輪驗證可逆，寫進 `tests/test_alembic_meeting_link.py`。
- 部署順序：merge migration → backend deploy → frontend deploy；無 data backfill。
- Rollback：若 migration 已跑但後續有問題，down 直接 drop table；唯一風險是使用者已建的 link 會消失，但 v1.1 是新功能，rollback 早期可接受。

## Open Questions

- 「related」link 在 `meeting-detail-layout` 的擺放位置：放在 prev/next nav 之下、metadata 兩欄之上是預設方案；apply 時實測若 header 過長可改為 collapsible，本 slice 保留 spec 寬度允許微調。
- DELETE 行為選 404 vs 204 idempotent：本 slice 採 **404 not_found** 比較有 debug 價值；若 apply 時發現 frontend 雙擊造成 UX 噪音，可改 204 + 前端 silently no-op。
