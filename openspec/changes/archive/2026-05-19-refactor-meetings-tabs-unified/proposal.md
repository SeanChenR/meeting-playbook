## Why

Kanban 與 Calendar 兩個視角目前是兩條獨立 route，切換時整個 route component 重新掛載，視覺上是「跳頁」而非 tab 切換。同時 view tab 跟 panel 的 header 三欄擠在一起，pill 滑動會被 panel 重 mount 中斷。需要重整成單一 route + 共用 tab 列 + 動畫切換，才能讓 view 切換符合 tab 的語意。

## What Changes

- `/meetings/calendar` route **BREAKING** 移除；舊 URL 不再可用（個人 side project，無書籤需保留）。
- `/meetings` 接受 `?view=kanban|calendar` search param 決定視角，預設 `kanban`。
- `MeetingsViewTabs` 從 panel header 拉出，獨立一排於 wrapper 上方；切換改寫 search param 而非 navigate pathname。
- Kanban / Calendar 內容抽成 `MeetingsKanbanPanel` / `MeetingsCalendarPanel`，於 `AnimatePresence` 中以水平 slide（方向跟 pill 一致）切換。
- `/meetings/new?from=calendar` 完成 / 取消改跳 `/meetings?view=calendar`。

## Non-Goals

- 不處理 meeting detail 頁面（`/meetings/$id`）的排版重整 — 另開 change。
- 不引入新的 view（保持 Kanban + Calendar 兩種）。
- 不調整 Calendar panel 內的 month/week 子 tab 行為。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `meetings-calendar-view`: URL contract 從 `/meetings/calendar` 改為 `/meetings?view=calendar`；shared tab bar 改由 `/meetings` wrapper 持有，不再雙 mount。

## Impact

- Affected specs: `meetings-calendar-view`
- Affected code:
  - Modified:
    - packages/web/src/route-tree.tsx
    - packages/web/src/components/meetings-view-tabs.tsx
    - packages/web/src/components/meetings-view-tabs.test.tsx
    - packages/web/src/routes/meetings/list.tsx
    - packages/web/src/routes/meetings/list.test.tsx
    - packages/web/src/routes/meetings/calendar.tsx
    - packages/web/src/routes/meetings/calendar.test.tsx
    - packages/web/src/routes/meetings/new.tsx
    - packages/web/src/routes/meetings/new.test.tsx
    - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - New:
    - packages/web/src/routes/meetings/kanban-panel.tsx
    - packages/web/src/routes/meetings/calendar-panel.tsx
  - Removed: (none — `calendar.tsx` 重構為 panel，保留檔名)
