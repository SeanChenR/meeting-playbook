<!--
每個 task 描述都必須含：
- 完成後可觀察的行為 / 契約（不是「修檔案 X」）
- 完成驗證方式（測試名 / CLI / lint / 人工 walkthrough）

檔案路徑只是定位用，task 仍須說明可觀察行為。
-->

## 1. Task 0 — Vendor install spike (Decision 1: Task 0 spike — vendor install 可行性先驗證)

- [x] 1.1 在試驗分支裝 `@animate-ui` base dialog、magicui `animated-theme-toggler`、shadcnblocks `calendar-standard-3`，並驗證 **Vendor install spike SHALL gate the production primitive work**：CLI add 不報 peer dep 衝突、`bun run build`、`bunx tsc --noEmit`、dev server 啟動三項通過、Tailwind v4 `bg-(--color-surface)` 寫法在新元件內可解析；驗證方式對齊 design 內 acceptance criteria — spike 分支三條 CLI 各回 exit 0 並截圖 / log 留檔，shadcnblocks license header 確認非 Pro tier，否則暫停 production task 並回報 — 同時對應 design「Decision 1: Task 0 spike — vendor install 可行性先驗證」決策。
- [x] 1.2 在 spike 內試裝一個 animate-ui Dialog 在任一 ProtectedShell route 嘗試開關，並確認背景 backdrop blur 8px 與 `var(--color-surface)` token 透過 Tailwind v4 解析正確（驗證 design 內 behavior contract 第 1 條 dialog 行為）；驗證方式：DevTools 檢視 computed style + 人工開關一次；同時對 design 內列出的 failure modes（vendor CLI install 失敗 / Tailwind v4 不相容 / shadcnblocks Pro tier）先試 trigger 看 spike 是否如預期擋下 production work，scope boundaries (in / out) 內列為 in-scope 的 spike 範圍。

## 2. Dialog 全站升級 — animate-ui motion

- [x] 2.1 新增測試 `packages/web/src/components/ui/dialog.smoke.test.tsx` 斷言 **Dialog and AlertDialog SHALL use animate-ui motion with Aura tokens** 的 behavior contract：mount 後 `[role="dialog"]` 存在、computed `background-color` 解析到 `var(--color-surface)`、backdrop element 有 `backdrop-filter: blur(8px)`，先紅。
- [x] 2.2 重寫 `packages/web/src/components/ui/dialog.tsx` 底層為 animate-ui base dialog，token 全走 CSS variable，prefers-reduced-motion 時退化為 instant；驗證：2.1 測試轉綠 + `bun --filter @meeting-playbook/web test` 整體不退化（acceptance criteria — 0 regression）。
- [x] 2.3 把現有 Dialog callsite (`meeting-link-picker.tsx`、`playbook-pane.tsx` AlertDialog 區段、其他 audit 出來的 surface) 統一從 `@/components/ui/dialog` barrel import；data shapes 與 scope boundaries (in / out) 不動 — 行為驗證：既有 e2e selectors（`data-testid`、`role="dialog"`、accessible name）仍解析；驗證：`bun --filter @meeting-playbook/web test` 內既有 dialog-related 測試全綠。

## 3. Popover barrel + callsite sweep (Decision 6: Popover barrel + 既有 callsite 一律走 barrel)

- [x] 3.1 新增 `packages/web/src/components/ui/popover.tsx` 暴露 `Popover` / `PopoverTrigger` / `PopoverContent` / `PopoverAnchor`，底層 animate-ui base popover，token 走 CSS variable；對應 spec **Popover SHALL ship via a barrel and use animate-ui motion** 與 design「Decision 6: Popover barrel + 既有 callsite 一律走 barrel」決策；驗證：smoke test 在 `primitives-smoke.test.tsx` 內 mount + visible + 無 raw hex（acceptance criteria 內列出）。
- [x] 3.2 把 `tags/tag-picker.tsx`、`chunk-action-menu.tsx`、`speaker-color-popover.tsx`、`transcript-chunk-row.tsx` 從 `@radix-ui/react-popover` 直接匯入改為 `@/components/ui/popover` barrel；行為驗證：tag picker 開合、transcript chunk action menu 開合動作不變、既有 e2e selector 解析 — 對應 design behavior contract 第 2 條；驗證：相關元件測試（包含 `transcript-pane` / `chunk-action-menu` 既有測試）全綠 + grep 確認 feature 元件無 `@radix-ui/react-popover` 直接 import。

## 4. Tooltip 全站 audit + barrel rewrite (Decision 7: 全站 hover-info icon button audit + Tooltip 強制掛載)

- [x] 4.1 重寫 `packages/web/src/components/ui/tooltip.tsx` 底層為 animate-ui primitives/animate/tooltip，token 套 inverse（background `var(--color-foreground)`、text `var(--color-background)`）；驗證：tooltip smoke test 在 `primitives-smoke.test.tsx` 補一條，斷言 hover 後 tooltip 出現且 computed colour 反相（acceptance criteria — 視覺對齊 DESIGN.md §4）。
- [x] 4.2 全站 audit 並補 Tooltip wrapper：`recording-badge.tsx`、`capture-indicator.tsx`、`rerun-button.tsx`、`theme-toggle.tsx`、`locale-toggle.tsx`，外加 audit 過程中發現的其他 icon-only button；對應 spec **Tooltip SHALL wrap every hover-info button across the app** 與 design「Decision 7: 全站 hover-info icon button audit + Tooltip 強制掛載」決策；驗證：在每個 audit target 寫 / 更新 testing-library hover assertion，且 i18n key `ui.tooltip.*` 全部在兩個 locale 檔同步存在 (`locales.test.ts` parity guard pass — design Decision 8: Test 策略 — smoke + variant + i18n parity 之一環)。

## 5. Determinate Progress

- [x] 5.1 新增 `packages/web/src/components/ui/progress.tsx` 套用 animate-ui base progress，fill 用 `var(--color-primary)` / track 用 `var(--color-surface-2)`，支援 `value` (0..100) + `aria-label` 對齊 data shapes；對應 spec **Determinate Progress SHALL use animate-ui base progress**；驗證：smoke test 斷言 `value=42` 時 `[role="progressbar"][aria-valuenow="42"]` + fill 計算寬度 ~42% 且 computed colour 為 `var(--color-primary)`（acceptance criteria 內列出的 progress behavior）。

## 6. Indeterminate Loading port (Decision 3: Indeterminate Loading port 自 uiverse `rare-pug-90`)

- [x] 6.1 新增 `packages/web/src/components/ui/loading.tsx` port `https://uiverse.io/gustavofusco/rare-pug-90` 為 React + Tailwind，動畫色換 `var(--color-primary)`、檔頂註解標 `Source: ... (CC0)`、支援 `size` (sm/md/lg) + `aria-label` 對齊 data shapes、prefers-reduced-motion 時退化為靜態 dot 或 Skeleton（design failure modes 內列出）；對應 spec **Indeterminate Loading SHALL be a ported uiverse animation in Aura purple** 與 design「Decision 3: Indeterminate Loading port 自 uiverse `rare-pug-90`」決策；驗證：smoke test 兩條（一個 default motion 斷言動畫 class 存在；一個 mock reduced-motion media query 斷言靜態 fallback 出現） + grep 無 raw hex 殘留（acceptance criteria）。

## 7. Theme toggler 換 magicui (Decision 4: Theme toggler 改 magicui animated-theme-toggler — 從三段改兩段)

- [x] 7.1 重寫 `packages/web/src/components/theme-toggle.tsx` 改用 magicui `animated-theme-toggler`，UI 只暴露 dark↔light、`ThemeProvider` 型別保持 `"light" | "dark" | "system"` 不動（scope boundaries (in / out) — 不破壞 persistence backward compat）；對應 spec **Theme toggler SHALL be the magicui animated reveal switch limited to two states** 與 design「Decision 4: Theme toggler 改 magicui animated-theme-toggler — 從三段改兩段」決策；驗證：testing-library 測試 — fresh session 點 toggle 一次後 `documentElement[data-theme]` 由 `"dark"` 變 `"light"` 且 `localStorage.mp-theme` 寫入明確值（不寫 `"system"`），再點變回 `"dark"`；i18n key `ui.themeToggle.label` / `toLight` / `toDark` 在兩 locale 同步（acceptance criteria）。

## 8. Toast 4 semantic variant (Decision 2: 4 個 Toast semantic variant 走 wrapper，不重寫 sonner)

- [x] 8.1 重寫 `packages/web/src/components/ui/sonner.tsx` 暴露 `toast.info` / `.success` / `.warning` / `.error` 並以 `data-type` + stripe 顏色綁 P1 的 `--color-info` / `--color-success` / `--color-warning` / `--color-danger` semantic token；新增 `packages/web/src/components/ui/toast-variants.tsx` 暴露 `<ToastInfo>` / `<ToastSuccess>` / `<ToastWarning>` / `<ToastError>` JSX wrapper 對齊 data shapes 列出的 `SemanticToastOptions`；對應 spec **Toast SHALL expose four semantic variants tied to Aura semantic tokens** 與 design「Decision 2: 4 個 Toast semantic variant 走 wrapper，不重寫 sonner」決策；驗證：smoke test 四條，每條呼叫對應 helper、斷言 toast DOM 有 `data-type="<variant>"` 與對應 token 顏色 stripe。
- [x] 8.2 把所有既有 `toast(...)` callsite (`export-meeting-button.tsx`、`playbook-pane.tsx`、`offline-ingest/UploadDialog.tsx`、其他 grep 出來的位置) 改成 semantic helper（成功用 `.success`、錯誤用 `.error`、提示用 `.info` / `.warning`）— 對應 design behavior contract 第 7 條 Toast 4 variant；行為驗證：對應元件既有測試（`export-meeting-button.test.tsx` 等）改完仍綠 + grep `toast\(` 不應命中 feature component 內未指定 variant 的呼叫（保留 legacy passthrough 只供漏網場景 — design failure modes）。

## 9. Calendar picker — date + time 拆兩欄 (Decision 5: Calendar picker — datetime-local 拆成「date picker + time input」雙欄)

- [x] 9.1 新增 `packages/web/src/components/ui/calendar.tsx` 套 shadcnblocks `calendar-standard-3`、token 走 Aura、檔頂註解標 source URL 對齊 acceptance criteria license attribution；對應 spec **Date selection in meeting forms SHALL use the Aura calendar picker** 與 design「Decision 5: Calendar picker — datetime-local 拆成「date picker + time input」雙欄」決策；驗證：smoke test mount + 選 today + 切月可達。
- [x] 9.2 把 `packages/web/src/components/meeting-edit-form.tsx` 與 `packages/web/src/routes/meetings/new.tsx` 的 `<input type="datetime-local">` 改成 `<Calendar />` (date) + `<Input type="time" />` (time)，submit 仍合成 ISO datetime 不破 backend payload 形狀（design behavior contract 第 8 條 + scope boundaries (in / out) — backend payload 不動）；驗證：更新 `meeting-edit-form.test.tsx` — `getByLabelText("date")` 選日期、`getByLabelText("time")` 改時間後 submit，斷言 mock fetch 接到的 `scheduled_start_at` 為合成 ISO 字串；i18n key `ui.calendar.openPicker` / `clear` / `today` 兩 locale 同步。

## 10. Sweep — i18n parity, lint, build (Decision 8: Test 策略 — smoke + variant + i18n parity)

- [x] 10.1 補齊所有新增 i18n key (`ui.toast.*` / `ui.themeToggle.*` / `ui.calendar.*` / `ui.tooltip.*`) 同時進 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json`，對應 design「Decision 8: Test 策略 — smoke + variant + i18n parity」決策；驗證：`bun --filter @meeting-playbook/web test packages/web/src/locales/locales.test.ts` deep-equal guard 綠（acceptance criteria 之一條）。
- [x] 10.2 整 change 收尾驗證 — 對齊 design 內 acceptance criteria 全部清單：`bun run lint` / `bunx tsc --noEmit` 0 error、`bun --filter @meeting-playbook/web test` 整體綠（含新增 smoke / variant / parity 測試）、`bun run build` 通過、人工 walkthrough 確認 prefers-reduced-motion OS 設定下 Dialog / Popover / Tooltip / Progress / Loading / Theme toggle 動畫全部退化、grep 確認 feature 元件無 `@radix-ui/react-popover` 直接 import 且無 raw hex 殘留在新元件 className；同時把 spec delta 內列出的 9 個 Requirement 走 `spectra validate` + `spectra analyze` 一次，確認 scope boundaries (in / out) 內 in-scope 全部覆蓋、out-of-scope 一個沒誤踩（含 backend / DB / P3 effect-layer / P4 routing / P5 detail layout / single-channel-recording-entry）。
