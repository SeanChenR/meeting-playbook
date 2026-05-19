## Why

DESIGN.md Section 4 列了 8 個 base UI primitive 升級（Dialog / Popover / Tooltip / Progress / Loading / Theme toggler / Toast / Calendar picker）。P1 (`ui-overhaul-aura-tokens`) 只翻 token，沒換組件；P3 effect-layer、P4 IA refactor 都依賴新 primitive。本 change 是 4-step roadmap 第 2 段：替換 `packages/web/src/components/ui/` 與 callsite 的 base primitive 為 animate-ui / magicui / shadcnblocks 對應元件，並 port uiverse `rare-pug-90` loading 動畫到 React，全部消費 P1 的 Aura token，使其他 phase 有底層可堆。

## What Changes

- **BREAKING**：`packages/web/src/components/ui/dialog.tsx`、`popover` 引入點、`tooltip.tsx`、`progress`（新檔）底層改寫為 animate-ui 元件；既有 callsite (`meeting-link-picker` / `playbook-pane` AlertDialog / `tag-picker` / `chunk-action-menu` / `speaker-color-popover` 等) 仍透過 barrel import，行為等價但 motion 改變
- 新增 `packages/web/src/components/ui/popover.tsx`（目前 callsite 在用裸 `@radix-ui/react-popover`，要先抽 barrel 再換 animate-ui）
- 新增 `packages/web/src/components/ui/progress.tsx`（determinate）— animate-ui/base/progress
- 新增 `packages/web/src/components/ui/loading.tsx`（indeterminate）— port uiverse `gustavofusco/rare-pug-90` 為 React + Tailwind + Aura purple token
- 全站 hover-info button / icon button 必須掛 `<Tooltip>`（DESIGN.md §4 「Mounted everywhere a hover would reveal supplementary info」），這次 change 涵蓋既有元件審計加上去
- **BREAKING**：`packages/web/src/components/theme-toggle.tsx` 由 DropdownMenu 改成 magicui `animated-theme-toggler`（圓形 reveal），i18n key 縮減（不再 cycle light/dark/system，改成 toggle dark↔light + 獨立 system reset action 或省略 system 三段，由 design 決定一個）
- 新增 4 個 Toast variant wrapper：`<ToastInfo>` / `<ToastSuccess>` / `<ToastWarning>` / `<ToastError>`，各自 stripe 顏色綁 P1 的 `--color-info` / `--color-success` / `--color-warning` / `--color-danger` semantic token；現有 `import { toast } from "sonner"` callsite 改 `toast.info(...)` / `toast.success(...)` 風格
- 新增 `packages/web/src/components/ui/calendar.tsx` — shadcnblocks `calendar-standard-3`；`meeting-edit-form.tsx` 與 `routes/meetings/new.tsx` 內的 `datetime-local` 拆成「日期 picker (calendar) + 時間 input」雙欄
- 新增 i18n keys (zh-TW + en parity)：`ui.toast.info` / `ui.toast.success` / `ui.toast.warning` / `ui.toast.error` aria-label、`ui.themeToggle.label`、`ui.calendar.openPicker` / `ui.calendar.clear`
- 新增 Task 0 spike：先在現有任一頁試裝 animate-ui dialog + magicui theme toggler，確認 CLI install、Tailwind v4 token override、build 無 dependency 衝突，再展開 production tasks

## Non-Goals

- 不動 P1 已落地的 token / `index.css` / Aura colour catalogue
- 不引入 P3 effect-layer 元件（Stars background / Animated list / Bar visualizer / Transcript viewer / Card hover / Button hover / Input curvy-earwig / Success result / Glass dock）
- 不動 P4 routing (`/calendar/upcoming` / `/recordings` / settings sub-nav)
- 不重排 meeting detail layout（屬 P5，已 deferred）
- 不動 `openspec/changes/single-channel-recording-entry/` 或 S27 相關檔案
- 不動 backend / API / DB schema；尤其禁止任何 `'them'` 字串塞進 DB 欄位（`me`/`counterparty` invariant）
- 不替換 domain-specific 自寫元件（TranscriptChunk / CaptureIndicator / ChatBubble / Pane wrapper / SpeakerColorPopover wrapper logic）— 它們 wrap 的底層 primitive 換掉就好，外層 API 不動
- 不引入 shadcnblocks Pro / 付費 block；只用 free tier `calendar-standard-3` snippet（授權需在 Task 0 spike 驗證）
- 不重寫 sonner 本身（仍是底層引擎，只是上層加 semantic wrapper）
- 不寫 production code 邊界外的 e2e / Playwright 改寫（保留現有 selector）

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ui-design-system`：新增 Aura-aware base primitive 元件契約（animate-ui Dialog / Popover / Tooltip / Progress、ported indeterminate Loading、magicui animated-theme-toggler、shadcnblocks Calendar、4 個 Toast semantic variant）。涵蓋既有 `Five shadcn primitives` requirement 的延伸與部分覆寫（tooltip / sonner 仍存在但行為延展）。

## Impact

- Affected specs: `ui-design-system`（delta only）
- Affected code:
  - New:
    - `packages/web/src/components/ui/popover.tsx`
    - `packages/web/src/components/ui/progress.tsx`
    - `packages/web/src/components/ui/loading.tsx`
    - `packages/web/src/components/ui/calendar.tsx`
    - `packages/web/src/components/ui/toast-variants.tsx`（`ToastInfo` / `ToastSuccess` / `ToastWarning` / `ToastError`）
  - Modified:
    - `packages/web/src/components/ui/dialog.tsx`（底層改 animate-ui/base/dialog）
    - `packages/web/src/components/ui/tooltip.tsx`（底層改 animate-ui/primitives/animate/tooltip）
    - `packages/web/src/components/ui/sonner.tsx`（暴露 semantic toast helper，stripe 取 semantic token）
    - `packages/web/src/components/theme-toggle.tsx`（改 magicui animated-theme-toggler）
    - `packages/web/src/components/meeting-link-picker.tsx`（Dialog 換新）
    - `packages/web/src/components/playbook-pane.tsx`（AlertDialog 重點 sweep；含 toast 改 semantic helper）
    - `packages/web/src/components/tags/tag-picker.tsx`（直接從 radix-popover 改 barrel）
    - `packages/web/src/components/chunk-action-menu.tsx`、`speaker-color-popover.tsx`、`transcript-chunk-row.tsx`、`transcript-pane.tsx`（Popover 改 barrel + animate-ui motion）
    - `packages/web/src/components/meeting-edit-form.tsx`、`packages/web/src/routes/meetings/new.tsx`（date 改 Calendar + time input）
    - 所有現有 `toast(...)` callsite（`export-meeting-button.tsx` / `playbook-pane.tsx` / `offline-ingest/UploadDialog.tsx` 等）改 `toast.info` / `.success` / `.warning` / `.error`
    - 全站含 hover-info 的 icon button：審計後加 `<Tooltip>` wrapper（包含 `recording-badge.tsx` / `capture-indicator.tsx` / `rerun-button.tsx` / `theme-toggle.tsx` / `locale-toggle.tsx` 等）
    - `packages/web/src/locales/zh-TW.json` + `packages/web/src/locales/en.json`（新增上述 i18n keys，parity guard 把關）
    - `packages/web/package.json`（新依賴：`@animate-ui` 或對應 install command 確認後的套件 / `magicui` CLI add）
  - Removed:
    - `packages/web/src/components/ui/dropdown-menu.tsx` 不刪（locale-toggle 仍用），只是 theme-toggle 不再用它
- Affected APIs / DB: 無
- Risk surface:
  - animate-ui / magicui CLI install 跟現有 shadcn / radix 依賴衝突的可能性
  - uiverse `rare-pug-90` 是 CSS keyframe snippet，需手動 port + 重配色，沒授權檔（uiverse 標 CC0 / public domain，仍 PR 內標 source URL 留證）
  - shadcnblocks `calendar-standard-3` 屬 free tier，但 license header 要 Task 0 仔細看，避免誤踩 Pro block
  - 既有 8 個 Toast callsite 換到 semantic helper 不能漏；i18n parity guard 防漏譯
