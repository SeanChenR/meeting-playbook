GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/26
Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
Blocked by: #25 (S15 meeting-edit) + #20 (S17 tags) — apply 必須等兩張 issue 都 archived 後才能解禁；propose 階段可先進行。

## Why

目前 `/home` 留下大量 placeholder（stat cards 寫死、recent meetings 為假資料、slice-1 留下的 backend confirmation debug block 仍掛在頁面上），`/dashboard` 路由根本不存在。資訊架構（IA）也與使用者實際工作流程脫節：登入後落點不是「今天要開的會」，而是還沒填上資料的空殼首頁。本 slice 一次處理兩件事——重整 IA、把 `/dashboard` 接上真資料——讓登入後第一眼就能看到今日會議、進行中錄音、待處理項目，並提供以週／月／六個月為單位的會議分析中心。

## What Changes

- **路由重整**：`/` 取代 `/home` 成為登入後首頁；`/home` 廢除（前端不再保留路由，舊連結回 `/`）；login redirect 從 `/home` 改為 `/`。
- **NavBar 重塑**：左側為 logo + 首頁（`/`）+ Meetings（`/meetings`）+ Dashboard（`/dashboard`）；Settings / locale / theme / logout 全部收進右上 user menu。
- **首頁 `/` 四個 region**：今日會議（依 `scheduled_start_at` 升冪）、進行中錄音（`meeting.status = "in_progress"`）、待處理（已上傳音檔待 ingest，或已完成但無 summary）、最近編輯（最後 3 筆 `updated_at`）；額外加上 Quick action buttons（新會議 / 從 Calendar 匯入）與 2FA 警告 banner（未啟用時顯示，啟用後消失）。
- **首頁清理**：移除既有 stat cards placeholder、recent meetings 假資料、slice-1 留下的 backend confirmation debug block。
- **Dashboard `/dashboard`**：4 張卡（月會議數 / 平均時長 / 活躍會議數 / Top counterparty）、Top counterparties bar、Tag 分佈 donut、6 個月會議數量趨勢 line；期間切換 toggle（本週 / 本月 / 過去 6 個月）。
- **新後端 endpoint**：`GET /api/meetings/stats?range=this_week|this_month|last_6_months` 由 `DashboardStatsQuery` deep module 提供（TDD：date math + 時區邊界）。
- **前端 charting**：引入 Recharts；色票走 `--primary` / `--accent` CSS variables，雙主題自動切換。
- **i18n**：所有新字串同步進 `zh-TW.json` 與 `en.json`，包含 stats、period switcher、empty states、2FA banner。
- **既有 testid 對應修正**：`navbar-*` 系列 testid 跟著 NavBar 重塑同步調整。

## Non-Goals

- **不做即時更新**：stats endpoint 為 request-time 計算，不引入 WebSocket / SSE 推播。
- **不做使用者偏好儲存**：期間 toggle 預設值固定為「本月」，不寫進使用者 settings。
- **不做 export**：Dashboard 不支援 CSV / PDF 匯出。
- **不做跨會議 KPI**：不計算 talk-time ratio、win rate、follow-up 完成率等業務 KPI；本 slice 只做會議數、平均時長、counterparty 頻率、tag 分佈、月度趨勢。
- **不做 `/home` 301**：舊路由直接從 router 移除，不掛 redirect；既有 e2e 引用 `/home` 的測試一起更新。
- **不引入新 chart library**：只用 Recharts，不評估 Visx / Chart.js / ECharts。
- **不重排 Settings**：Settings 子頁內部結構維持原樣，只是入口從 NavBar 移到 user menu。

## Capabilities

### New Capabilities

- `dashboard-stats`: `/dashboard` 頁面與 `GET /api/meetings/stats` endpoint 的契約——期間定義、回應 schema、`DashboardStatsQuery` deep module 的 date math / 時區邊界規則、tie-break 規則、UI rendering。
- `home-route`: `/` 首頁路由的版面、四個 region 的資料來源、Quick actions、2FA banner 顯示規則、login redirect 行為。

### Modified Capabilities

- `meeting-management`: 新增「為 stats 提供查詢支援」的 requirement（counterparty display name 計數、tag 計數、月度 bucket 計數）。

## Impact

- **Affected specs**: `dashboard-stats`（新）、`home-route`（新）、`meeting-management`（modified）。
- **Affected code**:
  - New:
    - packages/web/src/routes/HomePage.tsx
    - packages/web/src/routes/DashboardPage.tsx
    - packages/web/src/components/home/TodayMeetingsRegion.tsx
    - packages/web/src/components/home/InProgressRecordingsRegion.tsx
    - packages/web/src/components/home/PendingItemsRegion.tsx
    - packages/web/src/components/home/RecentlyEditedRegion.tsx
    - packages/web/src/components/home/QuickActions.tsx
    - packages/web/src/components/home/TwoFactorBanner.tsx
    - packages/web/src/components/dashboard/StatCards.tsx
    - packages/web/src/components/dashboard/TopCounterpartiesChart.tsx
    - packages/web/src/components/dashboard/TagDistributionChart.tsx
    - packages/web/src/components/dashboard/MonthlyTrendChart.tsx
    - packages/web/src/components/dashboard/PeriodSwitcher.tsx
    - packages/web/src/lib/api/stats.ts
    - packages/web/src/routes/HomePage.test.tsx
    - packages/web/src/routes/DashboardPage.test.tsx
    - packages/backend/app/queries/dashboard_stats.py
    - packages/backend/app/queries/tests/test_dashboard_stats.py
    - packages/backend/app/api/stats.py
    - packages/backend/app/api/tests/test_stats_endpoint.py
  - Modified:
    - packages/web/src/App.tsx
    - packages/web/src/components/NavBar.tsx
    - packages/web/src/components/UserMenu.tsx
    - packages/web/src/routes/LoginPage.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - packages/web/src/locales/locales.test.ts
    - packages/backend/app/main.py
  - Removed:
    - packages/web/src/routes/Home.tsx
    - packages/web/src/routes/home.test.tsx
- **New dependencies**:
  - `recharts` (frontend, runtime)
- **New env vars**: 無。`DashboardStatsQuery` 的時區固定假設為 server-local Asia/Taipei，不需要新 env。
- **Blocked by**: #25 (S15) 提供 meeting edit 對應的 `updated_at` 行為與最近編輯排序、#20 (S17) 提供 tag schema。Propose 可先 land；apply 解禁前需確認兩張 issue 已 archived。
