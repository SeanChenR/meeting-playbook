<!--
Blocked by: #25 (S15 meeting-edit) + #20 (S17 tags). apply 解禁前需確認兩張 issue 都 archived。
TDD discipline: 每個 task 都是 red → green → refactor 的最小單位；失敗測試先寫，再寫剛好讓它過的程式碼，最後 refactor。
-->

## 1. Backend — DashboardStatsQuery deep module（後端 query 抽象為 `DashboardStatsQuery` deep module）

- [x] 1.1 撰寫 `DashboardStatsQuery` 的 period boundary unit tests（依 **DashboardStatsQuery SHALL compute period boundaries in Asia/Taipei** 與 **Decision 3: Period 邊界語義**）：用 `FixedClock` 注入 2026-05-15 14:00、2026-01-01 00:30、2026-01-15 14:00 三組 fixture，驗證 `this_week` / `this_month` / `last_6_months` 半開區間起訖；驗收：`uv run pytest packages/backend/app/queries/tests/test_dashboard_stats.py::test_period_boundaries` 紅燈→實作後綠燈。
- [x] 1.2 [P] 撰寫 tie-break unit tests（依 **Top counterparty ranking SHALL use deterministic tie-breakers** 與 **Decision 4: Top counterparty tie-breaker**）：給定 `Acme=4, Initech=3, Soylent=3, NULL=2, ""=1` fixture，驗證 `top_counterparty == Acme`、`top_counterparties` 依 `count DESC, display_name zh-TW ASC, codepoint ASC` 排序、長度 ≤ 5、NULL/空字串被排除；驗收：`uv run pytest ...::test_top_counterparty_ties` 通過。
- [x] 1.3 [P] 撰寫空集合與 monthly_trend zero-fill unit tests（依 **DashboardStatsQuery deep module SHALL provide read-only aggregates over user's meetings**）：無會議使用者呼叫 `execute(user_id, "last_6_months")` 應回傳 6 個 zero-count buckets 升冪、`avg_duration_seconds is None`、`top_counterparty is None`、`tag_distribution == []`；驗收：`uv run pytest ...::test_empty_and_zero_fill` 通過。
- [x] 1.4 實作 `DashboardStatsQuery` 與 `Clock` / `SystemClock` / `FixedClock`（依 **Decision 2: 時區固定為 server-local `Asia/Taipei`** 與 **Decision 5: 後端 query 抽象為 `DashboardStatsQuery` deep module**）使所有 1.1–1.3 測試綠燈；observable behavior：`DashboardStatsQuery(session, clock).execute(user_id, range)` 回傳 `DashboardStats` dataclass，所有時區計算統一 `Asia/Taipei`，SQL 走 `AT TIME ZONE 'Asia/Taipei' + date_trunc`；驗收：1.1–1.3 三個 pytest 全綠 + `uv run ruff check packages/backend/app/queries/dashboard_stats.py` 無錯。

## 2. Backend — Stats endpoint 與 meeting list filters

- [x] 2.1 撰寫 `GET /api/meetings/stats` integration tests（依 **GET /api/meetings/stats SHALL return aggregated meeting statistics for the authenticated user filtered by range**、**Stats endpoint response SHALL conform to a stable JSON schema**、**Decision 6: API endpoint shape**）：以 FastAPI TestClient 覆蓋 `range=this_month` happy path、`range=last_year` → 400 `stats.invalid_range`、missing `range` → 預設 `this_month`、回應欄位型別符合 schema 表；驗收：`uv run pytest packages/backend/app/api/tests/test_stats_endpoint.py` 紅燈→實作後綠燈。
- [x] 2.2 實作 `app/api/stats.py` endpoint 並掛載至 `app/main.py`（依 **Decision 6: API endpoint shape**）使 2.1 全綠，behavior：經 Bun gateway 注入的 `X-User-Id` 為 scope key，response shape 對齊 schema；驗收：2.1 全綠 + `bun run lint` 對 `packages/backend` 無新警告。
- [x] 2.3 [P] 撰寫 `GET /api/meetings` 新 filter 的 integration tests 並擴充 endpoint 實作（依 **Meeting list endpoint SHALL support filters and ordering required by the home page regions**、**Decision 7: 首頁四個 region 各自呼叫既有 endpoint**）：覆蓋 `scheduled_date=YYYY-MM-DD`（Asia/Taipei 日界）、`status=in_progress`、`pending=true`、`order=scheduled_start_at:asc` / `order=updated_at:desc`、`limit=3`；驗收：`uv run pytest packages/backend/app/api/tests/test_meetings_list_filters.py` 全綠 + 維持原有 list 測試綠燈。

## 3. Frontend — 路由重整 + NavBar / UserMenu

- [x] 3.1 撰寫 router 切換測試並重塑 router（依 **The root route `/` SHALL render the user's home page after authentication**、**Frontend route contract**）：`packages/web/src/App.tsx` 把 `<HomePage />` 掛在 `/`、移除 `/home`、`<DashboardPage />` 掛在 `/dashboard`、`LoginPage` 成功後 `navigate("/")`；驗收：`bun --filter @meeting-playbook/web test src/App.test.tsx` 含「visit `/home` 顯示 not-found」「login 成功 navigate to `/`」兩個 case 全綠。
- [x] 3.2 [P] 撰寫 NavBar / UserMenu 測試並實作（依 **NavBar SHALL expose three top-level destinations and route auxiliary controls into a user menu**、**Decision 8: NavBar 與 UserMenu 分工**）：NavBar 顯示三個 link（`navbar-home-link` / `navbar-meetings-link` / `navbar-dashboard-link`），UserMenu dropdown 含四個 item（`usermenu-settings` / `usermenu-locale` / `usermenu-theme` / `usermenu-logout`），舊 `navbar-settings-link` 等 testid 不再出現；驗收：`bun --filter @meeting-playbook/web test src/components/NavBar.test.tsx src/components/UserMenu.test.tsx` 全綠 + `grep -r "navbar-settings-link\|navbar-locale-toggle\|navbar-theme-toggle\|navbar-logout" packages/web` 0 命中。

## 4. Frontend — Home page 四 region + Quick actions + 2FA banner

- [x] 4.1 撰寫並實作四個 region 元件（依 **Home page SHALL render four meeting regions**、**Decision 7: 首頁四個 region 各自呼叫既有 endpoint**）：`TodayMeetingsRegion` / `InProgressRecordingsRegion` / `PendingItemsRegion` / `RecentlyEditedRegion` 各自走 TanStack Query 並行 fetch，各有 loading / empty / error state；驗收：`bun --filter @meeting-playbook/web test packages/web/src/components/home` 全綠，含「empty state 使用 `home.*.empty` translation key」「單一 region error 不影響其他 region」case。
- [x] 4.2 [P] 撰寫並實作 Quick Actions + 2FA banner（依 **Home page SHALL render Quick Actions**、**Home page SHALL render a 2FA banner conditional on user state**、**Decision 9: 2FA Banner 顯示規則**）：`<QuickActions />` 含「新會議」與「從 Calendar 匯入」按鈕指向對應 route；`<TwoFactorBanner />` 僅在 Better Auth session `twoFactorEnabled === false` 時 render，包含到 `/settings/security` 的 CTA；驗收：`bun --filter @meeting-playbook/web test src/components/home/QuickActions.test.tsx src/components/home/TwoFactorBanner.test.tsx` 全綠，含「2FA 啟用後 banner 消失」case。
- [x] 4.3 撰寫 HomePage 整合測試並組裝（依 **Home page SHALL NOT render Slice 1 placeholder content**、**Observable behavior**）：`<HomePage />` 依序 render 四個 region + Quick Actions + 2FA banner，**沒有** legacy stat cards / 假 recent meetings / `data-testid="backend-confirmation"` debug block；移除 `packages/web/src/routes/Home.tsx` 與 `home.test.tsx`；驗收：`bun --filter @meeting-playbook/web test src/routes/HomePage.test.tsx` 全綠 + `grep -r "backend-confirmation" packages/web/src` 0 命中。

## 5. Frontend — Dashboard page

- [x] 5.1 引入 Recharts 並撰寫 stats client（依 **Decision 1: 採用 Recharts 為 chart library**）：在 `packages/web/package.json` 加 `recharts` runtime dep；`packages/web/src/lib/api/stats.ts` 提供 `useStatsQuery(range)` TanStack hook，wraps `GET /api/meetings/stats?range=...`；驗收：`bun install` 完成 + `bun --filter @meeting-playbook/web test src/lib/api/stats.test.ts` 覆蓋 happy path 與 400 error mapping 全綠。
- [x] 5.2 撰寫並實作 DashboardPage 四圖 + period switcher（依 **Dashboard page SHALL render four charts and a period switcher**、**Decision 10: TDD 順序（vertical slice）**）：`<StatCards />`（月會議數 / 平均時長 / 活躍會議數 / Top counterparty）、`<TopCounterpartiesChart />` bar、`<TagDistributionChart />` donut、`<MonthlyTrendChart />` line、`<PeriodSwitcher />` 三選項預設 `this_month`；切換 period 觸發 refetch；色票讀 `var(--primary)` / `var(--accent)` 雙主題自動切換；驗收：`bun --filter @meeting-playbook/web test src/routes/DashboardPage.test.tsx` 全綠，含「period 切換 refetch」「empty state 走 `dashboard.*` i18n」「light/dark theme 切換 chart 色票更新」case。

## 6. i18n + 驗證

- [x] 6.1 [P] 把所有新字串同步加入 `zh-TW.json` 與 `en.json`（依 **i18n contract**）：新增 `home.today.*` / `home.in_progress.*` / `home.pending.*` / `home.recently_edited.*` / `home.quick_actions.*` / `home.two_factor.*` / `dashboard.stat_cards.*` / `dashboard.charts.*` / `dashboard.period.*` / `dashboard.empty` / `errors.stats.invalid_range`；驗收：`bun --filter @meeting-playbook/web test src/locales/locales.test.ts` deep-equal 通過 + 無單側 locale 漏 key。
- [ ] 6.2 跑全套驗證並修正（依 **Acceptance criteria**、**Scope boundaries**）：`bun run lint`、`bun run test`、`cd packages/backend && uv run pytest`、`bun --filter @meeting-playbook/web build` 全綠；手動驗證 login → `/`、`/dashboard` 三 period 切換、2FA 啟用前後 banner 行為符合 spec；驗收：四個指令全綠且手動驗證 checklist 全 tick。
