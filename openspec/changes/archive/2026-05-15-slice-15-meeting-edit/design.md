## Context

Slice-11（archived）首次把 `PATCH /api/meetings/{id}` 接上來，但只接 `asr_provider` 一個欄位，schema `MeetingPatch` 與 repository `update_asr_provider_for_user` 都只服務這個用途。隨著 meetings UX revamp（archived）落地，Kanban、Calendar、List 三個視圖都依賴 `scheduled_start_at` 排序、分桶、顯示時間，但因為 `scheduled_start_at` 仍 nullable，三處都寫了 `scheduled_start_at ?? created_at` 的補丁邏輯，造成「沒設時間的 meeting 卡到 created bucket」這種令人困惑的視覺結果。

S15 要把 PATCH 變成真正的 inline edit endpoint（涵蓋 title、scheduled times、display names、asr_provider），同時把 `scheduled_start_at` 提升為必填欄位，掃除 fallback 分支。

`MeetingCreate.scheduled_start_at` 改必填屬 breaking change 對 API client 而言，但目前唯一的 client 是本 repo 的 `packages/web`，受控；對 DB 而言透過 backfill (`scheduled_start_at = created_at`) + `SET NOT NULL` 兩段式 migration，0 row 損失。

## Goals / Non-Goals

**Goals:**

- 單一 `PATCH /api/meetings/{id}` endpoint 接 6 個 optional 欄位，逐欄位驗證，部分欄位省略則該欄位不變
- `scheduled_start_at` 在 schema、DB、UI 都是必填；既有 NULL row 透過 migration 從 `created_at` backfill
- 移除 web 端三處 `?? created_at` fallback：`meeting-card.tsx`、`meetings-kanban.tsx`、`meetings-calendar-utils.ts`
- meeting detail 頁可 inline 編輯 title / scheduled times / display names（asr_provider 仍由現有 selector 處理）
- 既有 asr_provider PATCH 行為與 slice-11 落地的 router test 不退化
- 國際化字串雙 locale 同步增補；`locales.test.ts` deep-equal 不被破壞

**Non-Goals:**

- Soft-delete / 版本歷史 / undo — 採直接覆寫
- 修改 `status`、`calendar_event_id`、`started_at`、`ended_at` — 由 lifecycle / sync 自己寫
- WebSocket 即時推送 PATCH 結果給其他 tab — 仍走 client-side `invalidateQueries`
- Bulk PATCH 多筆 meeting
- 修改既有 archive change `slice-11` 內的 `update_asr_provider_for_user` repository 介面 — 改成新 `update_for_user` 取代，但保留語意相容路徑

## Decisions

### Endpoint 形狀：擴 `MeetingPatch` schema 為多欄位 partial update

`MeetingPatch` 由原本「只接 `asr_provider`」改為接 `{title?, scheduled_start_at?, scheduled_end_at?, counterparty_display_name?, me_display_name?, asr_provider?}`。所有欄位皆 `Optional`，未提供 = 不變。空 body（六個欄位都 None）回 200 + 當前 row（idempotent，沿用 slice-11 的 no-op 行為）。**Alternative considered**：拆成多個 sub-endpoint（`PATCH /api/meetings/{id}/schedule`、`/api/meetings/{id}/parties`）—— 被否決，前端 inline edit form 一次送多欄位較自然，且 REST 慣例 PATCH 本身就應支援 partial 多欄位。

### 字串欄位驗證：複用 `MeetingCreate._strip_and_require` 的策略

`title` / `counterparty_display_name` / `me_display_name` 在 PATCH body 出現時，沿用 `MeetingCreate` 的 `field_validator`：strip whitespace；strip 後為空字串 → 422。**Alternative considered**：允許空字串保留現有行為（什麼都不做）—— 被否決，空白字串送進來通常是 UI bug，靜默忽略會造成「我送了但沒生效」的疑惑。

### 時間欄位驗證：cross-field 驗 `end >= start`

當 PATCH body 同時帶 `scheduled_start_at` 與 `scheduled_end_at`，或只帶其中之一但 DB 已有另一邊，需驗證 `scheduled_end_at >= scheduled_start_at`，否則回 422 `meeting.invalid_time_range`。實作上在 router 層先 load 既有 row、合併 PATCH 值與既有值、再做最終驗證，避免 schema-only 驗證漏掉「只 PATCH end，但既有 start 比 end 晚」的 case。**Alternative considered**：schema 內 `model_validator` 一次擋掉 —— 對純 PATCH body 內兩欄都帶的 case 夠用，但漏掉「只 PATCH 一邊」的場景，所以還是需要 router 補一層。實作上兩層都做：schema 擋「body 兩欄都帶但顛倒」，router 擋「body + DB 合併後顛倒」。

### Repository: 新 `update_for_user(...)` 並 deprecate `update_asr_provider_for_user`

`MeetingRepository` 新增 `async def update_for_user(*, user_id, meeting_id, fields: dict[str, Any]) -> Meeting | None`，內部用 SQLAlchemy `update(Meeting).where(...).values(**fields)` 一個 SQL 寫完所有欄位。既有 `update_asr_provider_for_user` 保留但內部 delegate 到 `update_for_user(fields={"asr_provider": ...})`，slice-11 既有測試不退化。**Alternative considered**：保留 `update_asr_provider_for_user` 不動，再寫 6 個 `update_<field>_for_user` —— 被否決，欄位多時 SQL round-trip 暴增且耦合在 repo。

### Migration `0012_meeting_start_not_null`：先 backfill 再 SET NOT NULL

Upgrade 兩步：(1) `op.execute("UPDATE meeting SET scheduled_start_at = created_at WHERE scheduled_start_at IS NULL")`；(2) `op.alter_column("meeting", "scheduled_start_at", nullable=False)`。Downgrade 是 `op.alter_column("meeting", "scheduled_start_at", nullable=True)`（已 backfill 的值不還原回 NULL，因為已無法分辨原本是 NULL 還是真值）。**Alternative considered**：要求使用者先手動補 `scheduled_start_at` 再 migrate —— 被否決，使用者已累積數十筆無時間的 meeting，要求手動補違反 zero-touch upgrade 慣例。**Alternative considered**：保留 nullable 但前端 UI 強制必填 —— 被否決，那就只是把 fallback 邏輯藏到「前端永遠不送 null」的隱式約定，schema-level invariant 沒保住，後端排序仍要 fallback。

### 前端 inline edit form：react-hook-form + zod，獨立 component

在 `packages/web/src/components/meeting-edit-form.tsx` 寫獨立 component，receive `meeting: Meeting` + `onSaved: (updated: Meeting) => void`。內部用 react-hook-form 管表單 state、zod schema 驗證（與 backend 同樣規則）、submit 呼叫 `patchMeeting(id, payload)` API helper，成功後 react-query `invalidateQueries(["meetings"])` + `invalidateQueries(["meeting", id])`。Detail 頁直接 import 並 conditional render（toggle 按鈕切 view / edit 模式）。**Alternative considered**：用 inline editable cells（point-and-click 編輯）—— 被否決，多欄位同時編輯時 batch save 比逐欄位 PATCH UX 好且少 API call。

### 移除 `?? created_at` fallback：三處同步改

`meeting-card.tsx`：直接 `_formatTime(meeting.scheduled_start_at, i18n.language)`。
`meetings-kanban.tsx`：直接用 `meeting.scheduled_start_at` 排序。
`meetings-calendar-utils.ts`：移除 `if (!meeting.scheduled_start_at) return null` 的 short-circuit。
TypeScript 型別上 `Meeting.scheduled_start_at` 從 `string | null` 收緊為 `string`（既有 mock 資料同步更新）。**Alternative considered**：保留 fallback 不動以求保險 —— 被否決，本 slice 既然 schema 已升級為 NOT NULL，留 fallback 是技術債。

### Kanban 三欄分桶規則：從「時間窗口」改成「狀態 + 是否過期」

原本（meetings-ux-revamp 落地）的 bucket 規則用 7 天時間窗口分「即將到來 / 未來 / 已結束」，但這在 Sean 真實使用情境下產生兩個 UX 問題：(a) `scheduled_start_at` 過期且未開錄音的 meeting 跑到「已結束」欄，跟真的已完成的 meeting 視覺上混在一起；(b) 7 天 cutoff 抽象、跟「實際發生了什麼」無關。新規則改用「**狀態 + 是否過期**」三欄：

- **待補錄** (`needs_recording`)：`status === "scheduled" AND scheduled_start_at < now`。原排定時間已過但還沒開錄音，使用者應該補建會議記錄或刪除。Column accent: primary（demand attention）。
- **未來** (`upcoming`)：`status === "scheduled" AND scheduled_start_at >= now`。所有未發生的排定會議。Column accent: muted-foreground。
- **已結束** (`completed`)：`status in ("completed", "in_progress")`。**任何已被實際捕捉的 meeting**（包含正在錄音中與已 finalize 的）；不看 `scheduled_start_at`，因為一旦 session 啟動，「實際發生」比「原排定時間」優先。Column accent: secondary。

實作上重寫 `packages/web/src/lib/meetings-bucket.ts` 的 `getMeetingDateBucket(meeting, now)`：移除 `SEVEN_DAYS_MS` 與 `_startOfTodayLocal` 邏輯；新 bucket 型別 `MeetingDateBucket = "needs_recording" | "upcoming" | "completed"`；`now` 仍以參數傳入（測試用 frozen `Date`）。i18n key 雙 locale 同步改名：`meetings.kanban.bucketUpcoming/Future/Past` → `meetings.kanban.bucketNeedsRecording/Upcoming/Completed`，視覺左→右順序是 `needs_recording → upcoming → completed`（attention → future → archive）。`meetings-kanban.tsx` 的 `BUCKET_ORDER` 與 `BUCKET_LABEL_KEY` 同步改；過往 `_sortPastDesc` helper 改名 `_sortCompletedDesc`，仍以 `scheduled_start_at` desc 排「已結束」欄。

**Alternative considered**：保留 7 天窗口、再加第 4 欄「待補錄」—— 被否決，4 欄在 Kanban 視覺上太擠（每欄 ≥ 280px，達不到 narrow 螢幕的 baseline）；且「即將到來」與「未來」實質上沒有 actionable 差異。**Alternative considered**：用 `recording` 子表是否存在判斷「已結束」—— 被否決，需要 backend join 才能算，且 `meeting.status` 已經是現成的單一事實，session router 在 start/end 時已正確寫入。**Alternative considered**：把 `in_progress` 獨立成第 4 欄 —— 被否決，`in_progress` 通常壽命短（錄音中），獨立成欄空欄率高；當它出現時，使用者心智上跟「已被捕捉的會議」同類，跟 completed 同欄反而符合直覺。

### Edit form 改 Dialog 彈窗（取代 inline conditional render）

既有 detail 頁實作把 `<MeetingEditForm>` 用 `editFormOpen` state + conditional render 直接塞在 metadata-card 下方，這在表單填到一半時佔據主視覺 + 把下方 transcripts / playbook 推下去，UX 上是 distracting 的。改成 shadcn `<Dialog>` 中央彈窗：toolbar「編輯」按鈕仍是 trigger，`open` state 仍由 detail 頁管理，但 form 改 render 在 `<DialogContent>` 內，背景變半透明遮罩，主頁面不被推位。

實作：detail.tsx 把 `{meeting && editFormOpen && <MeetingEditForm ... />}` 改成 `<Dialog open={editFormOpen} onOpenChange={setEditFormOpen}><DialogContent>...<MeetingEditForm meeting={meeting} onSaved={() => setEditFormOpen(false)} onCancel={() => setEditFormOpen(false)} /></DialogContent></Dialog>`。`MeetingEditForm` 元件本身結構不變但移除外層 Card 包裹（Dialog 已提供 surface）；form `onSaved` 回呼仍負責關閉彈窗。Dialog header 用 `<DialogTitle>{t("meetings.edit.dialogTitle")}</DialogTitle>` + `<DialogDescription>{t("meetings.edit.dialogDescription")}</DialogDescription>`。新 i18n key：`meetings.edit.dialogTitle`（zh-TW「編輯會議」/ en「Edit meeting」）、`meetings.edit.dialogDescription`（zh-TW「修改 meeting 的標題、排定時間與顯示名稱」/ en「Update title, schedule, and display names」）。

**Alternative considered**：用 shadcn `<Sheet>`（右側滑出）—— 被否決，meeting edit form 只有 5 個欄位，Dialog 中央彈窗更符合「短表單」UX 慣例；Sheet 適合長表單或需保留背景 context 的場景。**Alternative considered**：保留 inline conditional render —— 被否決，user 直接 feedback 想要彈窗。

### Detail 頁 actions bar 內「上傳音檔」常駐顯示（取代 UploadBanner 條件顯示）

既有 `UploadBanner` 元件靠 `shouldShowOfflineIngestBanner(meeting, now)` 三條件決定是否 render（`status === "scheduled"` && `now > scheduled_end_at` && `recordings_available === false`），但這跟新 Kanban「待補錄」的語意有冗餘，且使用者語意是「上傳入口應該一直在」（特別是「待補錄」的 meeting 一定要有）。改成 `MetadataCard` 既有 button row 加 `uploadSlot?: React.ReactNode` prop，detail 頁傳入一個常駐「上傳音檔」按鈕，狀態無關都顯示。

按鈕 variant + disabled 規則：
- `status === "scheduled"`（含 needs_recording bucket）→ variant `"outline"`、enabled
- `status === "in_progress"` → variant `"outline"`、**disabled**（錄音中不允許併行上傳，避免雙寫 recording 子表）
- `status === "completed"` → variant `"secondary"`、enabled（用於重跑 ASR 場景，即使已有 transcript 也允許再上傳新音檔）

實作：新增 inline `<Button>` 元素（不另開元件，因為邏輯簡單）在 detail.tsx 用 `useMemo` 計算 `uploadVariant` / `uploadDisabled` 並傳 `uploadSlot={<Button ...>上傳音檔</Button>}` 到 MetadataCard。MetadataCard 內 button row 新加 `{uploadSlot && <div data-testid="metadata-upload-slot">{uploadSlot}</div>}` 渲染。`UploadBanner.tsx` 與 `UploadBanner.test.tsx` 刪除；`shouldShowOfflineIngestBanner` 函式一併刪除（無其它使用者）。`UploadDialog.tsx` 保留不動，仍由 detail 頁 `offlineIngestOpen` state 控制 open/close。

新 i18n key：`meetings.session.uploadAudio`（zh-TW「上傳音檔」/ en「Upload audio」）。舊 `offline_ingest.banner.heading` / `subhead` / `cta` 三個 key 在雙 locale 刪除（無使用者，且 banner 元件本身被移除）。

**Alternative considered**：保留 UploadBanner、放寬條件成永遠顯示 —— 被否決，banner 形式佔 detail 頁一整橫條空間，跟使用者期待的「並列雙按鈕」不符。**Alternative considered**：另開一個 `<MeetingActionsBar>` 元件並把 MetadataCard 的 start/end button 一併遷出 —— 被否決，scope 擴張過大；既有 MetadataCard button row 已能容納雙按鈕。

### Kanban 「待補錄」欄 card hover-only 上傳 shortcut + 專屬空欄 CTA

「待補錄」欄的設計意圖是「醒目地告訴使用者：這些 meeting 該補錄但還沒補錄」，所以 card 本身需要 affordance 直接 jump 到 upload 流程，而不是「先點進 detail 才看到上傳按鈕」。實作上：

1. **MeetingCard 加 `showUploadShortcut?: boolean` prop**：當 true 時，card root 加 `group` className；右下角加一個 `<button>` 用 `opacity-0 group-hover:opacity-100 transition-opacity` 在 hover 時淡入；button 標 `meetings.kanban.uploadShortcut` (zh-TW「上傳音檔」/ en「Upload audio」)，點下後 `navigate({ to: "/meetings/$id", params: { id: meeting.id }, search: { action: "upload" } })`。
2. **detail.tsx 偵測 `action` query param**：mount 時 `const search = useSearch({ strict: false }) as { action?: string }`；若 `search.action === "upload"` 則 `useEffect` 內 `setOfflineIngestOpen(true)` 並清掉 query（`navigate({ search: { action: undefined }, replace: true })` 避免重整再次觸發）。
3. **MeetingsKanban 在 needs_recording 欄渲染 card 時傳 `showUploadShortcut={true}`**：`{visible.map((m) => <MeetingCard key={m.id} meeting={m} showUploadShortcut={bucket === "needs_recording"} />)}`。
4. **needs_recording 欄空欄 CTA**：MeetingsKanban 渲染 empty hint 時，當 `bucket === "needs_recording"` && `items.length === 0`，render `t("meetings.kanban.bucketNeedsRecordingEmpty")` 取代既有 `t("meetings.kanban.bucketEmpty")`。新 i18n key：zh-TW「目前沒有待補錄的會議」/ en「No meetings to follow up on」。

**Alternative considered**：點 card 上的 shortcut 直接開 `<UploadDialog>` inline —— 被否決，需要把 dialog state 提升到 Kanban level 並傳 meeting context，且 dialog 在 list 視圖開啟比在 detail 頁開啟更 confusing。**Alternative considered**：所有 card 都顯示 shortcut（不只 needs_recording）—— 被否決，scheduled 未來的 meeting 用「上傳音檔」沒語意（還沒發生何來音檔）；只在 needs_recording 顯示反映真實 actionable 場景。

## Implementation Contract

**In scope (apply 期間 must produce):**

- **Behavior**: `PATCH /api/meetings/{id}` 接受 `{title?, scheduled_start_at?, scheduled_end_at?, counterparty_display_name?, me_display_name?, asr_provider?}` 任意子集；未列欄位不變；驗證失敗 → 422 + i18n error_code；row 不屬該 user → 404。
- **Interface**:
  - `MeetingPatch` Pydantic model：6 optional fields，沿用 `MeetingCreate` 的 strip-and-require validator 處理 3 個字串欄位，新增 `model_validator(mode="after")` 擋 schedule_start > schedule_end 的同 body 顛倒。
  - `MeetingRepository.update_for_user(*, user_id: str, meeting_id: str, fields: dict[str, Any]) -> Meeting | None`：空 fields dict → 直接 `get_for_user` 回 row；非空則單一 UPDATE。
  - `MeetingCreate.scheduled_start_at: datetime`（移除 `| None = None`）。
  - Frontend `patchMeeting(id, body)` helper 在 `packages/web/src/lib/meetings-api.ts`：accept partial body，回 `MeetingDetailRead`。
  - Frontend `<MeetingEditForm meeting={...} onSaved={...} />` component。
  - Frontend `getMeetingDateBucket(meeting, now)` 重寫：return value `"needs_recording" | "upcoming" | "completed"`；rule = `status` + `scheduled_start_at` vs `now`（無 7 天窗口）。
  - Frontend Detail 頁 edit form：`<Dialog>` 包覆 `<MeetingEditForm>`，`open` state 仍由 detail 頁 `editFormOpen` 管理；ESC / 點背景 / cancel / saved 皆 close。
  - Frontend `<MetadataCard>` 新 prop `uploadSlot?: React.ReactNode`，渲染在既有 button row 內；同時刪除 `UploadBanner.tsx` 元件及對應測試。
  - Frontend `<MeetingCard>` 新 prop `showUploadShortcut?: boolean`，true 時 card hover 顯示「上傳音檔」 mini button，點下 navigate 到 `/meetings/$id?action=upload`；detail 頁讀 `action` query 自動開 upload dialog。
  - Frontend `<MeetingsKanban>` 在 `bucket === "needs_recording"` 時對 cards 傳 `showUploadShortcut={true}`；空欄時改用 `meetings.kanban.bucketNeedsRecordingEmpty` 取代 `bucketEmpty`。
- **Data**: Alembic migration `0012_meeting_start_not_null`：upgrade backfill from `created_at` + SET NOT NULL；downgrade DROP NOT NULL。`meeting_playbook/meetings/models.py` 把 `scheduled_start_at` 從 `Mapped[datetime | None]` 改 `Mapped[datetime]`。
- **Error codes** (新加 / 沿用):
  - `meeting.not_found`（既有）→ 404
  - `meeting.invalid_time_range`（新）→ 422
  - 字串欄位空白 → Pydantic ValidationError → 422，error_code 為 `meeting.invalid_field`
- **i18n keys** (雙 locale 同步): `meetings.edit.title`、`meetings.edit.scheduledStart`、`meetings.edit.scheduledEnd`、`meetings.edit.counterpartyDisplayName`、`meetings.edit.meDisplayName`、`meetings.edit.save`、`meetings.edit.cancel`、`meetings.edit.saved`、`errors.meeting.invalidTimeRange`、`errors.meeting.invalidField`；Kanban bucket rekey：`meetings.kanban.bucketUpcoming/Future/Past` 被移除，新加 `meetings.kanban.bucketNeedsRecording/Upcoming/Completed`；Section 8 新增：`meetings.edit.dialogTitle`、`meetings.edit.dialogDescription`、`meetings.session.uploadAudio`、`meetings.kanban.uploadShortcut`、`meetings.kanban.bucketNeedsRecordingEmpty`；同時刪除 `offline_ingest.banner.heading/subhead/cta` 三個 key。
- **Acceptance**:
  - `cd packages/backend && uv run pytest tests/meetings/test_endpoints.py -k patch` 涵蓋 6 個欄位各自 happy path、空 body、跨 user 404、time range 顛倒、空白字串 422、asr_provider 既有測試 0 regression。
  - `uv run pytest tests/test_alembic_meeting_scheduled_not_null.py` 跑 upgrade → downgrade → upgrade 三輪、且 backfill 後 0 row 仍 NULL。
  - `bun --filter @meeting-playbook/web test` 跑 `meeting-edit-form.test.tsx` 涵蓋 4 個 component scenario；`locales.test.ts` deep-equal 不破。
  - `bun --filter @meeting-playbook/web test packages/web/src/lib/meetings-bucket.test.ts` 重寫覆蓋新 3 欄規則：(a) `status="scheduled" + scheduled_start_at < now` → `needs_recording`；(b) `status="scheduled" + scheduled_start_at >= now` → `upcoming`；(c) `status="in_progress"` → `completed`；(d) `status="completed"` → `completed`；(e) 邊界 `scheduled_start_at == now` → `upcoming`；(f) 無效 ISO 字串 → `needs_recording` safe default + dev `console.warn`。
  - `bun --filter @meeting-playbook/web test packages/web/src/components/meeting-edit-form.test.tsx` 既有 3 scenario 改在 `<Dialog>` 內 mount（用 `userEvent` 點 toggle 開 dialog → 拿 form 元素），3 個 scenario 全綠。
  - `bun --filter @meeting-playbook/web test packages/web/src/routes/meetings/detail.test.tsx` 新增 `::test_upload_slot_renders_in_metadata_button_row`（scheduled meeting → upload button enabled outline；in_progress → disabled；completed → enabled secondary），既有 `::test_edit_toggle_renders_form` 改 assert dialog 存在。
  - `bun --filter @meeting-playbook/web test packages/web/src/components/meeting-card.test.tsx` 新增 `::test_card_hover_shows_upload_shortcut_when_prop_true`（render card with `showUploadShortcut={true}` → button mounted with `data-testid="meeting-card-upload-shortcut"`；點下 → navigate 帶 `action=upload`）。
  - `bun --filter @meeting-playbook/web test packages/web/src/components/meetings-kanban.test.tsx` 新增 `::test_needs_recording_empty_shows_custom_cta`（meetings=[] → `kanban-empty-needs_recording` 文字含 zh-TW「目前沒有待補錄的會議」）+ `::test_needs_recording_cards_carry_upload_shortcut`。
  - Manual: detail 頁點 Edit → 改 title → Save → Kanban / Calendar / List 三個視圖在 5 秒內顯示新 title。

**Out of scope (apply 不可擴張到):**

- 修改 `status` / `started_at` / `ended_at` / `calendar_event_id` PATCH 支援
- WebSocket 即時推送
- Bulk PATCH
- Soft-delete / undo / 版本歷史
- 移除 `update_asr_provider_for_user`（保留 delegate）

## Risks / Trade-offs

- **既有 NULL row 的 `created_at` 並非真正的「會議排定時間」** → 對 Sean 個人專案來說可接受（既有 row 多為測試 / 早期建立），且 backfill 後使用者仍可透過 inline edit 修正。若要避免「假時間污染 calendar 視圖」，apply 時可在 release notes 提醒使用者掃一遍既有 meeting。
- **Migration 中段 fail (backfill 成功但 SET NOT NULL 失敗) 不易回滾** → Alembic transaction 包整段 upgrade，PostgreSQL `ALTER COLUMN ... SET NOT NULL` 在同 transaction 內若 fail 會 rollback 整個 migration 含 backfill。實作時 Alembic migration 不使用 `op.execute("COMMIT")` 中斷 transaction。
- **`MeetingCreate.scheduled_start_at` 改必填是 breaking change** → 唯一 client `packages/web` 同 slice 內同步更新表單；外部 API 無 public client。release notes 標記。
- **react-hook-form + zod 是新 dependency？** → 不是，slice-04 / slice-05 已引入；無新 dep。
- **三個視圖的 `?? created_at` fallback 移除後若使用者跳過 migration 直接執行新 web build** → backend 已保證 `scheduled_start_at` NOT NULL，因此 web 一定拿得到值；migration 是 deploy 前置條件，README 與 root dev orchestrator 啟動時的 alembic upgrade hook 已強制。

## Migration Plan

1. `cd packages/backend && uv run alembic upgrade head` 跑 `0012_meeting_start_not_null`：backfill + SET NOT NULL，皆在單一 transaction 內。
2. 重啟 backend；舊 web build 仍能讀寫（schema 兼容，多帶幾個 PATCH 欄位也不影響）。
3. 部署新 web build；舊 client 端的 fallback 程式碼移除無回滾顧慮。
4. 觀察 1 週：若有任何 invalid_time_range / invalid_field 422 暴增 → 檢視前端 form validation 是否漏擋。
5. **Rollback**: 跑 `alembic downgrade -1`（DROP NOT NULL）+ revert web build 即可；既有 backfilled 值保留（無法區分），不影響功能。

## Open Questions

- detail 頁的 "Edit" 入口要放 toolbar 還是 inline 旁邊 pencil icon？走 toolbar 統一處理（與 archived `meeting-detail-layout` 規範對齊）。
- 既有 `update_asr_provider_for_user` 是否可在下一個 slice 移除？保留至少一輪 release（slice-15 + slice-16）後再評估。
