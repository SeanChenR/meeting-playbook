## Context

PRD #16 第三波 IA / Analytics 收尾。S15 (meeting edit) + S17 (tags) 都是本 slice 的前置：S15 提供「最近編輯」所需的 `updated_at` 行為，S17 提供 tag schema 讓 donut chart 有資料。Propose 階段可先 land，apply 解禁前需確認兩張 issue 都 archived。

當前 `packages/web/src/routes/Home.tsx` 仍是 Slice 1 的雛形：
- 有 stat cards placeholder（寫死 `0`）
- 有「recent meetings」假資料列表
- 有 Slice 1 留下的 backend confirmation debug block（顯示 `/api/health` 回應 JSON）
- 路由 mount 在 `/home`，登入後 redirect 到 `/home`

`/dashboard` 路由不存在；NavBar 直接把 Settings / locale / theme / logout 攤在水平 list 上，按鈕擠成一排。

本 slice 把這兩件事一次處理完。

## Goals / Non-Goals

**Goals:**

- 把 `/` 變成「今天要做什麼」的首頁——今日會議、進行中錄音、待處理、最近編輯、Quick actions、2FA banner。
- 新增 `/dashboard` 分析中心——月會議數、平均時長、活躍會議、Top counterparty stat cards + Top counterparties bar + Tag 分佈 donut + 6 個月會議數量趨勢 line + 期間切換 toggle。
- 提供 `GET /api/meetings/stats?range=...` endpoint，由 `DashboardStatsQuery` deep module 支撐，TDD 覆蓋 date math + 時區邊界 + tie-break。
- NavBar 重塑：左側純導航（首頁 / Meetings / Dashboard），Settings / locale / theme / logout 一律收進右上 user menu。
- 移除 `/home` 路由與所有 placeholder / debug 區塊。

**Non-Goals:**

- 不做 stats 即時推播（不引入 WebSocket / SSE for stats）；endpoint 為 request-time 計算。
- 不做使用者偏好儲存（period toggle 預設「本月」，不存使用者 settings）。
- 不做 CSV / PDF export。
- 不計算 talk-time ratio、win rate、follow-up 完成率等業務 KPI；本 slice 限定會議數、平均時長、counterparty 頻率、tag 分佈、月度趨勢。
- 不掛 301 redirect from `/home` → `/`；舊路由直接從 router 移除。
- 不評估 Recharts 以外的 chart library。
- 不重排 Settings 內部結構；只調整入口位置。

## Decisions

### Decision 1: 採用 Recharts 為 chart library

雙主題 design system 走 oklch CSS variables，Recharts 接受 props 注入色票，能直接吃 `var(--primary)` / `var(--accent)` / `var(--muted)`，且支援 SVG-based responsive container。考慮過 Visx、Chart.js、ECharts：

- Visx：bundle 大、學習曲線陡，本 slice 圖表簡單，不需要。
- Chart.js：canvas-based，雙主題切換時需手動 redraw，不如 SVG 直觀。
- ECharts：bundle ~900KB，過度。

Recharts 滿足需求且已被 React 生態廣泛驗證。

### Decision 2: 時區固定為 server-local `Asia/Taipei`

`DashboardStatsQuery` 所有 date bucket 計算（週起點、月起點、6 個月起點）一律以 `Asia/Taipei` 為基準。理由：

- 本專案 single user，user 在台灣；所有 meeting `scheduled_start_at` 已是 timezone-aware UTC，比對前統一 `astimezone(ZoneInfo("Asia/Taipei"))`。
- 不引入新 env var；若未來部署多時區則由 follow-up change 處理。
- Postgres 查詢的 bucket 計算統一使用 `AT TIME ZONE 'Asia/Taipei'` 後再 `date_trunc`，確保 SQL 與 Python 行為一致。

備選：依使用者 `Accept-Language` 或 browser timezone header 動態決定；被否決——本 slice 不要把行為與 client header 綁定。

### Decision 3: Period 邊界語義

| Range            | 起點（包含）                                                   | 終點（不包含）             |
| ---------------- | -------------------------------------------------------------- | -------------------------- |
| `this_week`      | 本週週一 00:00:00 `Asia/Taipei`                                | 下週週一 00:00:00          |
| `this_month`     | 本月 1 號 00:00:00 `Asia/Taipei`                               | 下月 1 號 00:00:00          |
| `last_6_months`  | 當前月 -5 個月，1 號 00:00:00 `Asia/Taipei`（即包含當月共 6 個月） | 下月 1 號 00:00:00          |

- 週起點固定週一（ISO 週）。
- `last_6_months` = 當月 + 過去 5 個完整月份，總計 6 個 calendar months。
- bucket 比對使用半開區間 `[start, end)`，避免月底跨日重複計算。

### Decision 4: Top counterparty tie-breaker

Top counterparties 依「Me 側 display name 出現頻率」遞減排序，計算對象為當前 range 內所有 meeting 的 `counterparty_display_name`（若為 `NULL` 或空字串則排除）。出現次數相同時：

- 第一層 tie-breaker：按 display name 字典序（locale-aware `strcoll` for zh-TW，等同 Postgres `ORDER BY counterparty_display_name COLLATE "zh_TW"` 或 Python `locale.strcoll`）遞增排序。
- 第二層 tie-breaker：以 display name 本身 ASCII codepoint 遞增（fallback，確保 deterministic）。

只回傳 top 5，不足 5 個則回傳實際數量。

### Decision 5: 後端 query 抽象為 `DashboardStatsQuery` deep module

放在 `packages/backend/app/queries/dashboard_stats.py`，介面：

```python
@dataclass(frozen=True)
class DashboardStats:
    range: Literal["this_week", "this_month", "last_6_months"]
    meeting_count: int
    avg_duration_seconds: float | None  # None if no meeting
    in_progress_count: int
    top_counterparty: TopCounterparty | None
    top_counterparties: list[TopCounterparty]      # max 5
    tag_distribution: list[TagBucket]              # all tags with count > 0
    monthly_trend: list[MonthlyBucket]             # always 6 entries for last_6_months; 1 for this_week/this_month

class DashboardStatsQuery:
    def __init__(self, session: AsyncSession, clock: Clock = SystemClock()):
        ...

    async def execute(self, user_id: str, range: str) -> DashboardStats:
        ...
```

`Clock` 介面注入便於測試固定時間；production 直接用 `SystemClock`，test 用 `FixedClock(datetime)`。

### Decision 6: API endpoint shape

`GET /api/meetings/stats?range={this_week|this_month|last_6_months}`：

```json
{
  "range": "this_month",
  "meeting_count": 12,
  "avg_duration_seconds": 2745.0,
  "in_progress_count": 1,
  "top_counterparty": {"display_name": "Acme Corp", "count": 4},
  "top_counterparties": [
    {"display_name": "Acme Corp", "count": 4},
    {"display_name": "Initech", "count": 3}
  ],
  "tag_distribution": [
    {"tag": "sales", "count": 7},
    {"tag": "discovery", "count": 3}
  ],
  "monthly_trend": [
    {"month": "2025-12", "count": 8},
    {"month": "2026-01", "count": 10}
  ]
}
```

無效 `range` → 400 `{"error_code": "stats.invalid_range", "message": "..."}`，未指定 → 預設 `this_month`。

### Decision 7: 首頁四個 region 各自呼叫既有 endpoint

不為首頁開新 endpoint，重用：

- 今日會議 → `GET /api/meetings?scheduled_date=YYYY-MM-DD&order=scheduled_start_at:asc`
- 進行中錄音 → `GET /api/meetings?status=in_progress`
- 待處理 → `GET /api/meetings?pending=true`（沿用 S14 已加的 filter；不存在則 fall back 為 `status=processing`）
- 最近編輯 → `GET /api/meetings?order=updated_at:desc&limit=3`

四個 region 並行 fetch（TanStack Query），各自獨立的 loading / empty / error state。

### Decision 8: NavBar 與 UserMenu 分工

- `NavBar.tsx`：左側 logo + 三個 nav link（`/`、`/meetings`、`/dashboard`），右側 `<UserMenu />`。
- `UserMenu.tsx`：dropdown 觸發點為 avatar；items 為 Settings、Language toggle、Theme toggle、Logout。所有 testid 統一 prefix `usermenu-*`。
- 既有 `navbar-settings-link` / `navbar-locale-toggle` / `navbar-theme-toggle` / `navbar-logout` testid → 改名為 `usermenu-settings`、`usermenu-locale`、`usermenu-theme`、`usermenu-logout`，所有引用同步更新。
- 新增 `navbar-home-link`、`navbar-meetings-link`、`navbar-dashboard-link` 三個 testid。

### Decision 9: 2FA Banner 顯示規則

`<TwoFactorBanner />` 在首頁顯示條件：使用者 `twoFactorEnabled === false`（從 Better Auth session 讀取）。啟用後 banner 自動消失，無需手動 dismiss。Banner 內含「啟用 2FA」CTA 連到 `/settings/security`。

### Decision 10: TDD 順序（vertical slice）

依序：
1. `DashboardStatsQuery` 期間邊界 + tie-break unit tests（純 Python，pytest）
2. `/api/meetings/stats` endpoint integration tests（FastAPI TestClient）
3. Frontend `api/stats.ts` query client unit tests（bun test）
4. `DashboardPage` 組件 tests（bun test + happy-dom）
5. `HomePage` 組件 tests（bun test + happy-dom）
6. NavBar / UserMenu 重塑 tests

## Implementation Contract

**Observable behavior**

- 登入後瀏覽器導向 `/`，首頁顯示四個 region + Quick actions + 2FA banner（未啟用時）。
- 直接訪問 `/home` → 404（router 不掛該路由；不做 redirect）。
- 點 NavBar「Dashboard」→ `/dashboard`，預設顯示「本月」資料。
- 期間 toggle 切換時，stat cards / charts 同步重新請求 `/api/meetings/stats` 並重渲染。
- 啟用 2FA 後返回 `/`，banner 不再出現。

**API contract**

`GET /api/meetings/stats?range=this_week|this_month|last_6_months`：

- Auth: 經 Bun gateway 注入 `X-User-Id`；FastAPI 信任 header。
- Response shape：見 Decision 6。
- Error responses：
  - 400 `{"error_code": "stats.invalid_range", "message": "..."}` — `range` 不在白名單。
  - 401 透過 gateway 攔截；endpoint 本身不返回 401。
- 預設值：`range` 缺省 → `this_month`。

**Period boundary contract**

| Range            | Start (inclusive)                    | End (exclusive)         | Bucket granularity |
| ---------------- | ------------------------------------ | ----------------------- | ------------------ |
| `this_week`      | 本週週一 00:00 Asia/Taipei           | 下週週一 00:00          | 1 個 bucket（整週） |
| `this_month`     | 本月 1 號 00:00 Asia/Taipei          | 下月 1 號 00:00         | 1 個 bucket（整月） |
| `last_6_months`  | 當月 -5 個月 1 號 00:00 Asia/Taipei  | 下月 1 號 00:00         | 6 個 bucket（每月） |

- 週起點：ISO 週，週一。
- `monthly_trend` 永遠回傳對應 bucket 數量；無資料月份 `count: 0`，月份 key 為 `YYYY-MM`。
- 比對使用半開區間 `[start, end)`。

**Top counterparty tie-breaker contract**

- 排序：`count DESC, display_name COLLATE "zh_TW" ASC, display_name ASC`（最後一層為 deterministic fallback）。
- 排除：`counterparty_display_name IS NULL OR display_name = ''`。
- `top_counterparty` 取第一筆；`top_counterparties` 取 top 5。

**Frontend route contract**

- `/`           → `<HomePage />`
- `/dashboard`  → `<DashboardPage />`
- `/home`       → not mounted
- `/login` 成功後 navigate(`/`)

**i18n contract**

新字串落於：
- `home.*` namespace：四個 region 標題、empty state、Quick action labels、2FA banner。
- `dashboard.*` namespace：stat card labels、chart titles、period switcher options、empty state、error message。
- `errors.stats.invalid_range`：400 對應字串。

所有 key 同時存在於 `zh-TW.json` 與 `en.json`；`locales.test.ts` deep-equal 驗證。

**Acceptance criteria**

- `bun --filter @meeting-playbook/web test` 全綠，包含 HomePage / DashboardPage / NavBar / UserMenu 測試。
- `cd packages/backend && uv run pytest packages/backend/app/queries/tests/test_dashboard_stats.py packages/backend/app/api/tests/test_stats_endpoint.py` 全綠，coverage ≥ 80%。
- `bun run lint` + `cd packages/backend && uv run ruff check` 無錯。
- 手動驗證：登入後 `/` 正確、`/dashboard` 三個期間切換正常、2FA 啟用前後 banner 行為符合 Decision 9。

**Scope boundaries**

In scope: `/` 與 `/dashboard` 兩個頁面、`GET /api/meetings/stats` endpoint、`DashboardStatsQuery` 模組、NavBar / UserMenu 重塑、i18n 雙 locale、`/home` 路由移除。

Out of scope: stats 即時推播、stats export、period 偏好儲存、新 chart library 評估、Settings 子頁重排、業務 KPI（talk-time / win rate / follow-up）、`/home` redirect。

## Risks / Trade-offs

- [Risk] Postgres `AT TIME ZONE 'Asia/Taipei'` 與 Python `ZoneInfo("Asia/Taipei")` 邊界不一致（例如 DST，雖然 Taipei 無 DST 但仍要驗證） → Mitigation: TDD 覆蓋月首跨日 + 週日週一交界 + 6 個月區間頭尾 fixture，雙端比對 SQL bucket 與 Python bucket 相同。
- [Risk] Recharts bundle size（gzip ~95KB）增加 web bundle → Mitigation: 用 `import { LineChart, BarChart, PieChart } from "recharts"` 走 tree-shake；驗證 production bundle diff < 100KB gzip。
- [Risk] NavBar testid 大量改名 → Mitigation: design 中明列舊→新對照表；apply 階段先 grep 所有引用後再改名，避免遺漏。
- [Risk] 首頁四個 region 並行 fetch 觸發四個 API request，初次載入 waterfall → Mitigation: 都走 TanStack Query 並行；後續若 perf 成問題再做 batch endpoint（本 slice 不做）。
- [Risk] `last_6_months` 在 2026 跨年時 bucket 順序錯亂 → Mitigation: 月份 bucket 以 `YYYY-MM` 字串排序，使用 `(year, month)` tuple 比較；TDD fixture 包含 2025-08 → 2026-01 跨年案例。
- [Risk] S15 / S17 尚未 archived 時，apply 會缺少 `updated_at` 行為 / tag schema → Mitigation: propose 階段 park 該 change；apply 啟動前確認兩張 issue 都 archived。
