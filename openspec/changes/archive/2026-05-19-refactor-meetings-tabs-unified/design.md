## Context

`/meetings` 與 `/meetings/calendar` 目前是兩條獨立 TanStack Router route，各自掛載 `<MeetingsViewTabs>` 並 navigate 到對方 pathname。User-perceived 行為是「換頁」而非 tab 切換：

1. 整個 route component unmount / remount，無過場
2. `MeetingsViewTabs` 也跟著 unmount / remount，pill 滑動被打斷
3. 兩個 panel header 都是 `[title+meta] [tabs] [actions]` 的 3 欄 grid，但 actions 區段內容不同（Kanban 沒有 month/week + prev/next）

Side project 目前無外部書籤、無 email 連結指向舊 URL，可直接移除 `/meetings/calendar` route 而非保留 redirect。

## Goals / Non-Goals

**Goals:**

- `/meetings?view=kanban|calendar` 為 view 切換的唯一 URL contract；切換 view 不觸發 route remount
- `MeetingsViewTabs` 在整個 `/meetings` 生命週期持續 mount，pill 從點擊瞬間即流暢滑動
- Panel 切換以方向感知的水平 slide（Kanban → Calendar：新 panel 從右滑入；反之從左）
- Spec `meetings-calendar-view` 與 code URL contract 同步

**Non-Goals:**

- 不調整 meeting detail（`/meetings/$id`）的排版（另開 change）
- 不引入新 view 類型（如 list / timeline）
- 不調整 Calendar panel 內的 month/week 子 tab 行為
- 不為舊 URL 保留 redirect（個人 side project，無書籤需保留）

## Decisions

### Decision 1: 共用 wrapper 模式

`/meetings` route component (`MeetingsList`) 變成 wrapper，負責：

- 解析 `?view` search param（預設 `kanban`）
- 渲染獨立一排的 `<MeetingsViewTabs>`（不再嵌在 panel header 內）
- 在 `<AnimatePresence>` 中根據 `view` 切換 `<MeetingsKanbanPanel>` / `<MeetingsCalendarPanel>`

Alternative 拒絕：保留兩條 route + 在 `<Outlet>` 外包 `AnimatePresence` — TanStack Router 對 outlet 動畫支援不足，且仍會 unmount tabs。

### Decision 2: Panel 抽取

從 `routes/meetings/list.tsx` 與 `routes/meetings/calendar.tsx` 抽出兩個 panel 元件：

- `routes/meetings/kanban-panel.tsx` 匯出 `MeetingsKanbanPanel`
- `routes/meetings/calendar-panel.tsx` 匯出 `MeetingsCalendarPanel`

Panel 自己持有 header 兩側（title + actions）與內容，**不再 mount `MeetingsViewTabs`**。

Alternative 拒絕：把整段 inline 在 wrapper — wrapper 會肥到難維護；且各 panel header 的 actions 區段差異大。

### Decision 3: Search param 切換語意

`MeetingsViewTabs.handleChange` 改為：

```
navigate({
  to: "/meetings",
  search: prev => ({ ...prev, view: next === "kanban" ? undefined : "calendar" })
})
```

`view=undefined` 時 URL 為 `/meetings`（不顯式帶 `?view=kanban`），維持預設值不污染 URL。

### Decision 4: 動畫方向

Wrapper 用 ref 記住前一個 view，計算切換方向：

- `kanban → calendar`：dir = +1（exit 往左、enter 從右）
- `calendar → kanban`：dir = -1（exit 往右、enter 從左）

Variants：`enter: { x: dir * 40, opacity: 0 }` → `center: { x: 0, opacity: 1 }` → `exit: { x: dir * -40, opacity: 0 }`，spring transition stiffness 300 / damping 30。

使用 `AnimatePresence mode="wait"` 確保舊 panel 完全 exit 後才 enter，避免兩個 panel 同時佔據空間。

### Decision 5: BREAKING URL 移除

`/meetings/calendar` 從 `route-tree.tsx` 完全移除，**不**保留 `beforeLoad: redirect`。

Rationale：個人 side project 無外部書籤；redirect 留下「為什麼有兩條 URL」的疑惑，code 也多。

## Implementation Contract

**Behavior**

- 載入 `/meetings`：顯示 Kanban panel，view tabs 顯示 Kanban 為 active
- 載入 `/meetings?view=calendar`：顯示 Calendar panel，view tabs 顯示 Calendar 為 active
- 載入任何其他 `?view=<value>`：fallback 為 Kanban
- 載入 `/meetings/calendar`：route 不存在，TanStack Router 顯示 not found（個人 side project 可接受）
- 點 view tab：pill 滑到目標、500ms 內 panel 水平 slide 換成新內容；URL `?view` 同步更新（瀏覽器歷史一筆）
- 切換 view 時 `?tag_ids=` 等其他 search param 須保留（沿用現有 search-merge 邏輯）
- 從 `/meetings/new?from=calendar` submit → `/meetings?view=calendar`；cancel link href 也指向 `/meetings?view=calendar`

**Interface / data shape**

- `MeetingsViewTabs` props 不變（仍接 `value: "kanban" | "calendar"`）。新增的「來自 wrapper 的 `view`」由 wrapper 傳入
- 新元件 `MeetingsKanbanPanel`、`MeetingsCalendarPanel` 無 prop（內部各自 useQuery）

**Failure modes**

- `?view` 帶非預期值（如 `?view=list`）：fallback Kanban，不 throw
- AnimatePresence 在 reduced-motion 環境下 transition duration 設 0（沿用 `useReducedMotion`）

**Acceptance criteria**

- `bun --filter @meeting-playbook/web test` 全綠
- `meetings-view-tabs.test.tsx` 改寫的測試斷言：點 calendar trigger 後 `router.state.location.search.view === "calendar"`、pathname 仍為 `/meetings`
- `tag-filter-roundtrip.test.tsx` 改寫斷言：跨 view 切換時 `?tag_ids=` 保留
- 手動瀏覽器驗證：點擊 view tab 時 panel 滑動順暢、tab pill 不會閃爍
- `openspec/specs/meetings-calendar-view/spec.md` 內所有 `/meetings/calendar` URL 字串已替換

**In scope:**

- 上述 affected code / specs 全部
- 對應測試的 URL 斷言更新

**Out of scope:**

- meeting detail 排版重整
- 新增 view 類型
- Calendar panel 內部行為（month/week tabs、unscheduled 側欄）

## Risks / Trade-offs

- **Risk**: 移除舊 URL 後若有未發現的 hardcode（如未列出的測試、文件 example），會 404 → Mitigation：grep 全 repo `meetings/calendar` 字串，已盤點過列在 proposal Impact
- **Risk**: AnimatePresence + 兩個重 panel 同時存在的 frame 會跳到 layout 高度差 → Mitigation：`mode="wait"` 確保不重疊；若仍跳，wrapper 加 `min-h-[X]`
- **Risk**: spec 改動可能波及 `meeting-attachment/spec.md` 等其他 spec 對 calendar.tsx 檔案的引用 → Mitigation：那些是檔案路徑引用而非 URL，calendar.tsx 檔名保留為 panel 檔，不破壞引用

## Migration Plan

無 DB / runtime migration。部署只需前端重新 build 即可。Rollback 直接 revert commit。
