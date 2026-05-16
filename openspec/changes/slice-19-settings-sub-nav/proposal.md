> GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/29
> Parent PRD：https://github.com/SeanChenR/meeting-playbook/issues/16
> 依賴：Slice 18（IA reset，Issue #26）— propose 可先 land，apply 需等 S18 archive 後才解鎖

## Why

目前所有「設定」散落在多個 top-level route：`/calendar/import`（Calendar 連線）、`/settings/voice`（聲紋樣本）、`/settings/tags`（Slice 17 標籤），TOTP 安全控制甚至沒有專屬頁面。使用者要管理任一項都得從 navbar 拼湊路徑，沒有一個「設定中心」可以盤點全貌。此 slice 在 IA reset（Slice 18）落地後，把所有設定收進 `/settings` 雙欄 shell，並把 `/calendar/import` 搬進 `/settings/integrations`。

## What Changes

- 新增 `<SettingsLayout>` — 雙欄 shell，左側 sub-nav 常駐 7 個 sub-route：profile / security / voice / tags / integrations / preferences / data
- 新增 sub-routes：
  - `/settings/profile`：display-only，顯示 Better Auth session user 的 name / email / avatar
  - `/settings/security`：既有 TOTP 控制（從 navbar 入口收編；本 slice 不改 TOTP 行為）
  - `/settings/voice`：**wrap** Slice 13 已建好的頁面內容，外殼換成 `<SettingsLayout>`
  - `/settings/tags`：**wrap** Slice 17 已建好的頁面內容，外殼換成 `<SettingsLayout>`
  - `/settings/integrations`：把 `/calendar/import` 的 Calendar 連線狀態 UI 搬進來
  - `/settings/preferences`：最小可用版本 — language / theme / 預設 ASR provider 三個欄位
  - `/settings/data`：最小可用版本 — Recording window（30 天 read-only 顯示）、Export all data 按鈕、刪除帳號按鈕
- NavBar 右上 user menu 加「Settings」入口（連到 `/settings/profile`）
- **BREAKING**：`/calendar/import` 廢除為獨立路由，舊 URL 以 redirect 導向 `/settings/integrations`
- i18n 雙 locale：所有新字串同時加入 `zh-TW.json` 與 `en.json`

## Non-Goals

- 不擴充 TOTP 行為（搬進 `/settings/security` 但內容沿用既有元件）
- 不擴充 Slice 13 voice enrollment 內容（只是換外殼）
- 不擴充 Slice 17 tag management 內容（只是換外殼）
- 不實作 `/settings/data` 的 export all data 後端流程；本 slice 僅保留按鈕 + i18n 字串，實際匯出延後到獨立 change
- 不實作刪除帳號的後端流程；本 slice 僅保留按鈕，點擊顯示「coming soon」對話框
- 不調整 Recording window 的 30 天值（只顯示）
- 不變動既有 `/settings/voice` 的 URL（保持向後相容）
- 不在 navbar 直接放 Settings 區段；唯一入口是 user menu

## Capabilities

### New Capabilities

- `settings-shell`：定義 `<SettingsLayout>` 雙欄 shell、左側 sub-nav 結構、7 個 sub-route 的存在與導航行為，以及 user menu「Settings」入口的位置

### Modified Capabilities

- `calendar-integration`：Calendar 連線狀態 UI 的渲染位置從 `/calendar/import` 改為 `/settings/integrations`；舊 URL 必須 redirect

## Impact

- 受影響 specs：`settings-shell`（新增）、`calendar-integration`（修改）
- 受影響程式碼：
  - 新增：
    - `packages/web/src/routes/settings/layout.tsx`（`<SettingsLayout>` 雙欄 shell）
    - `packages/web/src/routes/settings/profile.tsx`
    - `packages/web/src/routes/settings/security.tsx`
    - `packages/web/src/routes/settings/integrations.tsx`
    - `packages/web/src/routes/settings/preferences.tsx`
    - `packages/web/src/routes/settings/data.tsx`
    - `packages/web/src/components/settings/sub-nav.tsx`
    - `packages/web/src/routes/settings/layout.test.tsx`
    - `packages/web/src/routes/settings/profile.test.tsx`
    - `packages/web/src/routes/settings/integrations.test.tsx`
    - `packages/web/src/routes/settings/preferences.test.tsx`
    - `packages/web/src/routes/settings/data.test.tsx`
    - `packages/web/src/routes/settings/redirect.test.tsx`（`/calendar/import` → `/settings/integrations`）
  - 修改：
    - `packages/web/src/route-tree.tsx`（註冊新 sub-routes、把 `/calendar/import` 改 redirect、把 `/settings/voice` 包進 layout）
    - `packages/web/src/routes/settings/voice.tsx`（外殼改用 `<SettingsLayout>`，內容不變）
    - `packages/web/src/routes/calendar/upcoming.tsx`（變成可被 `/settings/integrations` 重用的 component；移除 standalone route 邏輯）
    - `packages/web/src/components/navbar.tsx` 或 user menu 元件（加入「Settings」入口）
    - `packages/web/src/locales/zh-TW.json`、`packages/web/src/locales/en.json`（新增 `settings.*` namespace）
    - `packages/web/src/locales/locales.test.tsx`（locale 鍵相等性測試會自動覆蓋）
  - 移除：無（`/calendar/import` 邏輯搬遷而非刪除）
- 環境變數：無新增
