## 1. MeetingsViewTabs 切換改用 search param — Decision 3: Search param 切換語意

- [x] 1.1 寫紅燈測試：在 `meetings-view-tabs.test.tsx` 加 case「點 calendar trigger 後 router state 的 pathname 維持 `/meetings`、search 物件出現 `view: "calendar"`」；同時加「點 Kanban trigger 後 `view` 從 search 移除」。執行 `bun --filter @meeting-playbook/web test meetings-view-tabs` 應失敗。驗證：該檔測試 fail。
- [x] 1.2 [P] 改 `MeetingsViewTabs.handleChange`：呼叫 `navigate({ to: "/meetings", search: (prev) => ({ ...prev, view: next === "kanban" ? undefined : "calendar" }) })`；移除原本的 pathname 分支。觀察行為：點任一 trigger 即時更新 URL 的 `view` search param，pathname 永遠是 `/meetings`，其他 search param 保留。驗證：1.1 測試由紅轉綠。
- [x] 1.3 [P] 同步更新 `tag-filter-roundtrip.test.tsx`，斷言由 pathname 改為 search.view，符合 reciprocal toggle 行為（spec: Meeting list and calendar view are reachable via reciprocal toggle buttons）。驗證：`bun --filter @meeting-playbook/web test tag-filter-roundtrip` 綠燈。

## 2. 抽出 MeetingsKanbanPanel 與 MeetingsCalendarPanel — Decision 2: Panel 抽取

- [x] 2.1 建立 `packages/web/src/routes/meetings/kanban-panel.tsx`，匯出 `MeetingsKanbanPanel`，內含原 `list.tsx` 的 header 兩側（title+meta、actions）與 `<MeetingsKanban>` 內容；**不**含 `<MeetingsViewTabs>`。觀察行為：元件單獨渲染時不會出現 view tab 列，但 header 上的 bucket 計數、TagFilter、`+ 新會議` 按鈕、empty state、loading 文字皆與舊 `list.tsx` 一致。驗證：在新 `list.test.tsx` 用 `<MeetingsKanbanPanel>` 直接 mount 一次，斷言 `data-testid="meetings-list-meta"` 存在且不含 `data-testid="meetings-view-tabs"`。
- [x] 2.2 [P] 把原 `routes/meetings/calendar.tsx` 重構為匯出 `MeetingsCalendarPanel`（檔名保留以維持其他 spec 對檔案路徑的引用）：header 兩側留下年月 meta + month/week 子 tab + 導覽按鈕；移除 `<MeetingsViewTabs>` 的 mount。觀察行為：單獨渲染時不含 view tab 列，但月/週切換、prev/today/next、未排程側欄、empty state 皆與舊版一致。驗證：在 `calendar.test.tsx` 用 `<MeetingsCalendarPanel>` 直接 mount，斷言原有 `data-testid="calendar-tab-month"` / `calendar-tab-week` / `meetings-calendar-unscheduled` 仍存在且不含 `meetings-view-tabs`。

## 3. MeetingsList wrapper：共用 tab 列 + 動畫切換 — Decision 1: 共用 wrapper 模式 / Decision 4: 動畫方向

- [x] 3.1 寫紅燈測試 `list.test.tsx`：mount `/meetings` 路由，斷言（a）`data-testid="meetings-view-tabs"` 存在且位於 panel 之外、（b）`?view` 缺省時渲染 `meetings-kanban` 樹、（c）`?view=calendar` 渲染 calendar 樹、（d）`?view=foo` fallback 為 Kanban。驗證：該檔測試 fail（wrapper 尚未實作）。
- [x] 3.2 改寫 `routes/meetings/list.tsx` 為 wrapper `MeetingsList`：解析 `useSearch()` 取 `view` (default `kanban`、非法值 fallback `kanban`)；渲染獨立一排的 `<MeetingsViewTabs value={view} />`；其下用 `<AnimatePresence mode="wait">` 包 motion.div，根據 `view` 切換 `<MeetingsKanbanPanel>` 或 `<MeetingsCalendarPanel>`。觀察行為：URL `?view` 改變時，wrapper 同時更新 tab pill 與 panel；tab 元件保持同一 DOM instance（spec: /meetings and /meetings/calendar SHALL share a Kanban / 行事曆 tab bar）。驗證：3.1 測試由紅轉綠。
- [x] 3.3 加入方向感知的水平 slide：以 `useRef` 記住前一次 view，計算 `dir = view === "calendar" ? 1 : -1`；variants `{ enter: (d) => ({x: d*40, opacity:0}), center: {x:0, opacity:1}, exit: (d) => ({x: d*-40, opacity:0}) }`；transition spring stiffness 300 / damping 30；用 `useReducedMotion()` 將 transition duration 設為 0 以支援 prefers-reduced-motion（spec: View switch SHALL animate the panel without remounting the tab bar）。觀察行為：kanban→calendar 時新 panel 從右滑入、舊 panel 往左滑出，反之亦然；reduced-motion 下無滑動但 URL 仍更新。驗證：擴充 `list.test.tsx` 加一條 reduced-motion mock case，斷言 `motion.div` 接到 duration: 0；手動瀏覽器驗證滑動方向。

## 4. 移除 /meetings/calendar route — Decision 5: BREAKING URL 移除

- [x] 4.1 寫紅燈測試 `list.test.tsx`：用 `createMemoryHistory({ initialEntries: ["/meetings/calendar"] })` 建 router，斷言 `router.state.matches` 不含 calendar route 或進入 not-found（spec scenario: Legacy /meetings/calendar path is no longer registered）。驗證：該測試 fail（路由仍存在）。
- [x] 4.2 修改 `route-tree.tsx` 移除 `MeetingsCalendarPanel` 既有 component route（原 `meetingsCalendarRoute`）；同步更新 `import` 語句改指向 `kanban-panel` / `calendar-panel` 模組（如有需要）。觀察行為：應用啟動後 `/meetings/calendar` 不再被任何 route 匹配；型別檢查 (`bun tsc`) 通過。驗證：4.1 測試由紅轉綠；`bun --filter @meeting-playbook/web build` 成功（spec: GET /meetings/calendar renders the user's meetings on a month or week grid 已改為 `/meetings?view=calendar`）。

## 5. /meetings/new from=calendar 目的地更新

- [x] 5.1 改寫 `routes/meetings/new.test.tsx` 中四條 `from=calendar` 相關 case：cancel link `href` 斷言改為 `/meetings?view=calendar`、submit 後 `router.state.location` 斷言 pathname=`/meetings` 且 search.view=`calendar`（spec: NewMeeting SHALL honour ?from=calendar for redirect on submit and cancel）。驗證：執行該檔測試 fail（new.tsx 尚未更新）。
- [x] 5.2 [P] 修改 `routes/meetings/new.tsx`：`cancelHref` 從字串改為 TanStack `<Link to="/meetings" search={{ view: "calendar" }}>`；submit 後的 `navigate({ to: "/meetings/calendar", replace: true })` 改為 `navigate({ to: "/meetings", search: { view: "calendar" }, replace: true })`；註解內容同步更新指向新 URL。觀察行為：從 calendar panel 點 `+ 新會議` 走完整 round trip 回到 calendar panel，URL 為 `/meetings?view=calendar`。驗證：5.1 測試由紅轉綠。

## 6. 驗證與 spec 同步

- [x] 6.1 執行 `bun --filter @meeting-playbook/web test` 全綠（含 i18n locale 對齊測試）；若任何測試因舊 URL 斷言失敗，回到對應 group 處理。驗證：測試 summary 顯示 0 fail。
- [x] 6.2 啟動 web dev 伺服器（依 root README 的 dev 指令），手動在瀏覽器（with reduced-motion off）驗證：點 Kanban↔Calendar tab，pill 在點擊瞬間即滑動、panel 水平 slide 方向正確、`MeetingsViewTabs` DOM 不重建（Chrome DevTools Elements 面板查看 React fiber id 不變或元素 highlight 持續存在）；切到 `prefers-reduced-motion` 後 slide 消失但 URL 更新仍正常。觀察行為：tabs 切換不再有「跳頁」感。驗證：人工確認流暢度通過、發給 Sean review。
- [x] 6.3 [P] spec sync：本 change 的 `specs/meetings-calendar-view/spec.md` 已寫入新 URL contract（含 ADDED：View switch SHALL animate the panel without remounting the tab bar；MODIFIED 4 條）；archive 階段會合入 live spec。驗證：`spectra validate refactor-meetings-tabs-unified` 通過。
