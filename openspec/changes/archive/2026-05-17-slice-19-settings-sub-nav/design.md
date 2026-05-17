## Context

目前設定相關路由散落：

- `/calendar/import`（Slice 7）— Google Calendar 連線與 upcoming events 列表
- `/settings/voice`（Slice 13）— 聲紋樣本錄製
- `/settings/tags`（Slice 17）— 標籤管理（依 PRD 假設已存在）
- TOTP 控制 — 散在 `/totp/enroll` + `/totp/verify`，沒有「日常管理」入口
- profile / preferences / data — 完全不存在

`packages/web/src/route-tree.tsx` 仍是平面結構（17 個 top-level routes），沒有任何 layout route 把這些設定畫面包起來。NavBar 的 user menu 也沒有「Settings」入口。

Slice 18（Issue #26）負責 IA reset — 重新整理 navbar 與 top-level 導航結構，並建立 user menu 的基礎容器。**S19 在 S18 落地後接手**，把所有設定收進 `/settings` 雙欄 shell。

## Goals / Non-Goals

**Goals:**

- 提供唯一的「設定中心」入口：`/settings/profile` 為預設著陸 sub-route
- 統一外觀：所有 sub-route 共用 `<SettingsLayout>` 的雙欄 shell（左側 sub-nav 常駐、右側 content pane）
- 既有頁面零行為破壞：`/settings/voice`（S13）與 `/settings/tags`（S17）內容完全不變，只更換外殼
- `/calendar/import` 舊 URL 仍可用 — 用 redirect 把舊書籤 / 舊文件導向 `/settings/integrations`
- 最小可用 preferences 與 data sub-routes — 只有 UI + i18n 字串，沒有後端流程
- 雙 locale（zh-TW + en）必須同步

**Non-Goals:**

- 不擴充 TOTP enrollment / verify 行為（沿用 S1 既有元件）
- 不擴充 voice enrollment（S13）與 tag management（S17）行為
- 不實作 export all data 後端流程
- 不實作刪除帳號後端流程
- 不調整 Recording window 的 30 天值
- 不變動 `/settings/voice`、`/settings/tags` 的 URL（保持書籤相容）
- 不把任何設定區段放到 navbar；唯一入口仍是 user menu

## Decisions

### Decision 1：採用 TanStack Router 的 layout route，而非每個 sub-route 自帶 shell

`<SettingsLayout>` 是一個 layout route（路徑 `/settings`、`component: SettingsLayout`，內含 `<Outlet />`），所有 sub-routes 以 `getParentRoute: () => settingsLayoutRoute` 註冊。

理由：

- 雙欄 shell（左 sub-nav + 右 content）只渲染一次，sub-route 切換時左欄不重 mount，符合 TanStack Router 慣例
- sub-nav 的「目前在哪個 sub-route」狀態由 router 提供，不用每個 sub-route 各自 prop drilling
- 與既有 route-tree.tsx 的 code-based router 寫法一致（與 Slice 7、Slice 13 相同 pattern）

替代方案：每個 sub-route 內各自渲染 `<SettingsLayout>{children}</SettingsLayout>`。優點是不用動 route hierarchy；缺點是左欄會在每次路由切換時重 mount，動畫會閃，且 sub-nav 的 active state 要自己算。Rejected。

### Decision 2：`/calendar/import` 改 redirect，內容元件 inline 進 `/settings/integrations`

`packages/web/src/routes/calendar/upcoming.tsx` 目前是 standalone route component，內含「Google Calendar 連線狀態 + upcoming events 列表」。

執行策略：

- 把 `upcoming.tsx` 的 JSX 拆成 reusable component（例如 `<CalendarIntegrationPanel />`），檔案位置與名字本 slice 不搬遷以降低 diff 噪音
- `/settings/integrations` sub-route 直接 render `<CalendarIntegrationPanel />`
- `/calendar/import` 改成 `beforeLoad: () => throw redirect({ to: "/settings/integrations" })`，**不**保留原 component

替代方案：保留 `/calendar/import` 為獨立路由 + 在 `/settings/integrations` 內 iframe 嵌入。Rejected — iframe 會破壞 i18n、theme、auth state 共享。

替代方案 2：直接在本 slice 把 `upcoming.tsx` 改名為 `integrations.tsx` 並搬到 `routes/settings/` 底下。Rejected — 會讓 git blame / 既有測試一次全部失準，留給未來 cleanup change 處理。本 slice 只動 route registration 與 component 抽取。

### Decision 3：sub-nav 用 shadcn / animate-ui 既有元件，不引入新依賴

`<SettingsSubNav>` 用 `<NavigationMenu>`（shadcn）或單純 `<Link>` + `aria-current="page"` 的 `<nav>`。每個項目左邊放 animate-ui icon（profile=user、security=shield、voice=mic、tags=tag、integrations=plug、preferences=sliders、data=database）。

理由：CLAUDE.md UI conventions 規定「animated icons live in `packages/web/src/components/animate-ui/icons/`；no emoji in UI strings」。Sub-nav 是低互動頻率元件，用 plain `<Link>` + `lucide-react` 靜態 icon 也可接受；本 slice 採後者以避免動畫干擾使用者掃視。

### Decision 4：i18n namespace 分組

新增 `settings` 頂層 namespace，sub-route 各自一個 sub-namespace：

```
settings:
  nav: { profile, security, voice, tags, integrations, preferences, data }
  profile: { title, name, email, avatar_alt }
  security: { title, totp_enrolled, totp_not_enrolled, manage }
  integrations: { title, calendar_section_title }
  preferences: { title, language, theme, asr_provider, default_asr_provider }
  data: { title, recording_window_label, recording_window_value, export_all, delete_account, coming_soon }
```

`/settings/voice` 與 `/settings/tags` 既有 i18n 鍵保留不動（避免動 S13 / S17 既有測試），只新增 `settings.nav.voice` / `settings.nav.tags` 給 sub-nav 用。

### Decision 5：preferences sub-route 的三個欄位只做 UI，不持久化

language / theme / 預設 ASR provider 三個欄位顯示目前值，並提供 `<Select>` 控制：

- language：呼叫既有 `i18n.changeLanguage()`（已有持久化到 localStorage 的機制）
- theme：呼叫既有 theme toggle（Slice 14 ui-overhaul 已建立）
- 預設 ASR provider：**本 slice 只顯示 read-only 目前值**（從既有 `useASRProvider` 讀），切換功能保留給未來 change（避免動 backend `user.preferred_asr_provider` schema）

理由：preferences sub-route 是 MVP 殼，三個欄位的後端持久化各自有不同程度複雜度，硬塞進本 slice 會破壞「外殼搬家」的單一焦點。

### Decision 6：data sub-route 的兩個按鈕在本 slice 是「展示 + coming soon」

- Export all data：按下顯示 `<Dialog>` 內容為 `t("settings.data.coming_soon")`
- Delete account：同上
- Recording window：display-only，顯示 `30 days`（hardcode；未來若改可從 backend `RECORDING_RETENTION_DAYS` 拉，但本 slice 不接 API）

理由：實作後端流程需要新的 backend endpoints + auth flow + 不可逆操作確認 UX，遠超 IA 搬家 slice 範圍。Non-Goals 已明確排除。

## Implementation Contract

**觀察行為（end-user）：**

1. 登入後從 navbar 右上 user menu 點「Settings」→ 落在 `/settings/profile`，左欄顯示 7 個 sub-nav 項目
2. 點 sub-nav 任一項 → 右側 content pane 切換，URL 同步更新；左欄保持原樣（不重 mount）
3. 在 sub-nav 切到「Integrations」→ 看到原本 `/calendar/import` 看到的 Google Calendar 連線狀態與 upcoming events
4. 直接訪問 `/calendar/import` → 被 redirect 到 `/settings/integrations`（URL bar 更新）
5. 直接訪問 `/settings/voice` → 看到既有 S13 聲紋樣本錄製 UI（行為與外觀內容不變），但**外圍多了 SettingsLayout 雙欄 shell**
6. 直接訪問 `/settings/tags` → 看到既有 S17 標籤管理 UI，外圍同上
7. `/settings/preferences` 顯示 language / theme / 預設 ASR provider 三欄；前兩欄可切換，第三欄為 read-only
8. `/settings/data` 顯示 Recording window（`30 days`）、Export all data 按鈕（點擊顯示 coming-soon dialog）、Delete account 按鈕（同樣 coming-soon dialog）
9. zh-TW 與 en 切換時所有 settings 字串同步切換

**Route 介面：**

`packages/web/src/route-tree.tsx` 新增的 route nodes：

```ts
const settingsLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsLayout,
});

const settingsIndexRoute = createRoute({
  getParentRoute: () => settingsLayoutRoute,
  path: "/",
  beforeLoad: () => { throw redirect({ to: "/settings/profile" }); },
});

const settingsProfileRoute = createRoute({
  getParentRoute: () => settingsLayoutRoute,
  path: "profile",
  component: SettingsProfile,
});
// ... security / voice / tags / integrations / preferences / data 同 pattern

const calendarImportRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/calendar/import",
  beforeLoad: () => { throw redirect({ to: "/settings/integrations" }); },
});
```

`settingsVoiceRoute` 與 `settingsTagsRoute` 改成 `getParentRoute: () => settingsLayoutRoute` 並把 path 改成相對路徑 `voice` / `tags`（最終 URL 仍是 `/settings/voice` / `/settings/tags`）。

**Component 介面：**

- `<SettingsLayout />`：無 props，內含 `<aside><SettingsSubNav /></aside><main><Outlet /></main>`
- `<SettingsSubNav />`：無 props，內部用 `useRouterState()` 推算當前 sub-route 來決定 `aria-current`
- `<CalendarIntegrationPanel />`：從現有 `upcoming.tsx` 抽出；無 props，自行載入 connection state 與 upcoming events
- 各 sub-route component（Profile / Security / Integrations / Preferences / Data）皆為無 props 的 page component

**i18n 契約：**

- `packages/web/src/locales/zh-TW.json` 與 `en.json` 同步新增 `settings.*` namespace（見 Decision 4）
- `packages/web/src/locales/locales.test.tsx` 既有的「兩份 locale 鍵相等」測試會自動覆蓋；不需新增 i18n 測試

**失敗模式：**

- 未登入訪問 `/settings/*` → 沿用既有 auth guard（gateway 層 redirect 到 `/login`）
- `/settings/voice`、`/settings/tags` 內部錯誤 → 沿用 S13 / S17 既有 error boundary（不改）
- `/settings/integrations` 內 Google Calendar 連線失敗 → 沿用 `/calendar/import` 既有錯誤 UX（搬家不改錯誤行為）
- preferences sub-route 的 read-only ASR provider 欄位 → 若 user 沒有設定，顯示 `t("settings.preferences.asr_provider_default")` 字串

**驗收條件（apply 完成時必須通過）：**

1. `bun --filter @meeting-playbook/web test` 全綠，包含新增的 layout / 7 個 sub-route / redirect 測試
2. 手動驗收清單：上述 9 個 end-user 觀察行為 + zh/en 切換
3. `bun --filter @meeting-playbook/web lint` 全綠
4. 既有 `packages/web/src/routes/settings/voice.test.tsx` 與（若存在）`tags.test.tsx` 仍綠
5. 既有 `packages/web/src/routes/calendar/upcoming.test.tsx` 至少保留 redirect 測試（內容元件抽出後若 component 有獨立測試需求，另行新增 `calendar-integration-panel.test.tsx`）

**Scope 邊界：**

- **In scope**：route-tree 改動、`<SettingsLayout>` + `<SettingsSubNav>` 新元件、5 個新 sub-route 檔案、`upcoming.tsx` 抽 component、redirect、i18n 雙 locale 字串、所有新檔的單元測試
- **Out of scope**：TOTP 行為調整、voice enrollment 行為調整、tag management 行為調整、export all data 後端、刪除帳號後端、ASR provider 切換的後端持久化、Recording window 可變更、navbar 重新設計（屬 S18）、user menu 樣式調整（屬 S18，本 slice 只新增「Settings」項目）

## Risks / Trade-offs

- **Risk：S18 尚未 archive，apply 會被阻擋** → Mitigation：propose 階段先 land，apply 階段在 `/spectra-apply` 啟動時檢查 S18 狀態；若 S18 未 archive 則停下並告知使用者
- **Risk：`<SettingsLayout>` 改變 `/settings/voice` 與 `/settings/tags` 的外殼結構，可能讓既有測試的 DOM query 失準** → Mitigation：先跑現有測試 → 找到失敗的 selector → 用更穩定的 `getByRole` / `getByText` 取代 `getByTestId` 或 deep DOM query；若仍需大改既有測試，於 apply 階段告知並暫停
- **Risk：`/calendar/import` 改 redirect 會讓既有書籤短暫經歷 redirect 跳轉，影響 UX** → Mitigation：使用 TanStack `redirect()` 的 `throw` pattern，在 `beforeLoad` 階段就 redirect（不會先 render 任何中間頁面）
- **Risk：preferences 的 read-only ASR provider 欄位讓使用者誤以為「可以切換但失敗」** → Mitigation：欄位旁加 `<Badge>{t("settings.preferences.read_only")}</Badge>` 並在 placeholder 註記「coming soon」
- **Trade-off：選擇「外殼搬家、行為不變」而非「整體重新設計設定 UX」** → 接受 — 本 slice 焦點是 IA，UX polish 應為獨立 change
