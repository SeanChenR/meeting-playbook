## Context

DESIGN.md §4 把 UI 升級分四步：P1 翻 token、P2（本 change）動 base primitive、P3 加 effect-layer、P4 動 routing。P1 已假設先 ship — 它把 `index.css` 改成 dark-first Aura，提供 `--color-info` / `--color-success` / `--color-warning` / `--color-danger` semantic tokens 與 `--color-me` / `--color-them` 速色家族。

當前（reference: `packages/web/src/components/ui/`）：

- `dialog.tsx` / `alert-dialog.tsx` — 自寫 shadcn radix wrapper，無 animate-ui motion
- `popover` — 目前 callsite 直接 `import * as Popover from "@radix-ui/react-popover"`（`tags/tag-picker.tsx`），其他 `chunk-action-menu` / `speaker-color-popover` 也類似裸用，沒有 barrel
- `tooltip.tsx` — radix tooltip 薄殼，已存在但 callsite 稀疏
- progress / loading — 不存在
- `theme-toggle.tsx` — DropdownMenu cycle light/dark/system
- `sonner.tsx` — Toaster + re-export `toast`，無 semantic variant
- date input — `<input type="datetime-local">`（`meeting-edit-form.tsx`、`routes/meetings/new.tsx`）

新元件來源庫須先 spike：

- **animate-ui** (https://animate-ui.com)：shadcn-compatible CLI install (`npx shadcn add @animate-ui/...`)；Dialog / Popover / Progress 在 `/base/`，Tooltip 在 `/primitives/animate/`
- **magicui** (https://magicui.design)：shadcn-compatible CLI install；`animated-theme-toggler` 是圓形 reveal
- **shadcnblocks** (https://shadcnblocks.com)：shadcnblocks Pro 內含付費 block；`calendar/calendar-standard-3` 是 free tier 但需 Task 0 對 license 與 install command 核實
- **uiverse** (https://uiverse.io)：純 HTML/CSS snippet，CC0 license；`rare-pug-90` 需 port 為 React + Tailwind

## Goals / Non-Goals

**Goals:**

- 全站 Dialog / Popover / Tooltip / Progress / Theme toggler / Calendar picker 走新 vendor 元件，所有顏色透過 Aura token 而非 vendor 預設
- 新增 indeterminate Loading（port uiverse rare-pug-90）供 ASR model 下載、playbook 產生等不可估算進度時用
- 4 個 Toast semantic variant 取代既有 `toast(...)` 散落用法，stripe 顏色綁 semantic token，i18n parity 通過
- 全站 hover-info button / icon button 補上 `<Tooltip>`
- Task 0 spike 留下「vendor install 可行」的證據（一個試裝後刪除的 dev branch），再進 production task
- 既有測試（含 `primitives-smoke.test.tsx`、`meeting-edit-form.test.tsx`、`export-meeting-button.test.tsx`）不退化；新元件補 smoke test

**Non-Goals:**

- 不動 P1 token / `index.css`（包括 hue、chroma、新增 token；如必要請開分支 P1.x change）
- 不引入 P3 effect-layer（Stars background / Animated list / Bar visualizer / Transcript viewer / Card hover / Button hover / Input curvy-earwig / Success result / Glass dock）
- 不動 routing / route tree / settings sub-nav（P4）
- 不重排 meeting detail layout（P5 deferred）
- 不動 `openspec/changes/single-channel-recording-entry/`、不動 S27 capture entry
- 不動 backend / API / DB；尤其禁止 `'them'` 字串塞 DB 欄位（speaker enum 為 `me` / `counterparty`）
- 不引入 shadcnblocks Pro / 付費 block；只取 free tier `calendar-standard-3`
- 不重寫 sonner 本身；只在上層加 semantic wrapper
- 不重寫 domain-specific 元件（TranscriptChunk / CaptureIndicator / ChatBubble / Pane / SpeakerColorPopover wrapper logic）

## Decisions

### Decision 1: Task 0 spike — vendor install 可行性先驗證

Task 0 在試驗分支裝 `@animate-ui/base/dialog`、magicui `animated-theme-toggler`、shadcnblocks `calendar-standard-3`，目的：

1. CLI add 成功且 `package.json` lock 一致（無 peer dep 衝突）
2. Aura token override 可生效（Tailwind v4 `bg-(--color-surface)` 等語法在新元件內讀得到）
3. shadcnblocks free tier license header 對齊 MIT/Apache 系，可直接 commit
4. `bun run build` + `bunx tsc --noEmit` + dev server 啟動三項通過

驗證完整地保留 spike 結果（commit 草稿或文字 log）但 spike 程式碼不進 main；接著才開展 task 1 起的 production work。

**Alternatives considered**：
- A: 不 spike 直接寫 production code — 若 vendor install 失敗整段 work 卡死
- B (採用): Task 0 spike，先測 install
- C: 換成自寫 motion — 失去用 animate-ui 的意義

### Decision 2: 4 個 Toast semantic variant 走 wrapper，不重寫 sonner

新增 `packages/web/src/components/ui/toast-variants.tsx`：

```typescript
// 對外 API
import { toast } from "@/components/ui/sonner";

toast.info(t("ui.toast.info.label"), { description: "..." });
toast.success(t("ui.toast.success.label"), { description: "..." });
toast.warning(t("ui.toast.warning.label"), { description: "..." });
toast.error(t("ui.toast.error.label"), { description: "..." });
```

`sonner.tsx` 在 `toastOptions.classNames` 內按 `data-type` (info/success/warning/error) 套 stripe class，stripe 顏色綁 `--color-info` / `--color-success` / `--color-warning` / `--color-danger`。`<ToastInfo>` 等 component wrapper 是 jsx-friendly 別名（內部直接呼叫 `toast.info`）。

**Alternatives considered**：
- A: 完全換掉 sonner 改 animate-ui toast — 無對應元件，且 sonner 已穩定
- B (採用): sonner 留作引擎，semantic helper 包外殼
- C: 自寫 toast — 重複造輪子

### Decision 3: Indeterminate Loading port 自 uiverse `rare-pug-90`

uiverse `gustavofusco/rare-pug-90` 是 CSS-only 的 dot pulse 動畫。Port 步驟：

1. 抓原 CSS keyframes，搬到 `packages/web/src/components/ui/loading.tsx` 同檔案的 `<style>` 區（或抽到 `index.css` 的 `@keyframes mp-loading-*`）
2. 顏色從原作的灰白系改為 `var(--color-primary)`（Aura purple `#A277FF` dark / `#8464C6` light）
3. wrap 成 `<Loading aria-label={...} size="sm|md|lg" />` React component；接受 `className` 合併
4. 在動畫 element 加 `prefers-reduced-motion` 守衛 — reduced motion 時改為靜態 dot 或 `<Skeleton />` 視覺

授權：uiverse 標 CC0 / public domain；PR 內以註解標 source URL 留 audit trail。

**Alternatives considered**：
- A: 用 magicui shimmer — 屬 skeleton，不對應 indeterminate spinner 場景
- B (採用): port uiverse rare-pug-90
- C: 用 radix progress indeterminate state — animate-ui 已涵蓋 determinate，indeterminate 視覺感弱

### Decision 4: Theme toggler 改 magicui animated-theme-toggler — 從三段改兩段

magicui 元件是 dark↔light 兩段 reveal 動畫，沒 system 中間態。決策：

- **採用 (B)**：toggle 只做 `dark ↔ light`，捨棄 `system` 第三選項。`ThemeProvider` 仍保留 `theme: "light" | "dark" | "system"` 型別（避免 break breaking change），但 toggle UI 只暴露兩態。`system` 預設仍是 fresh session 邏輯（讀 `prefers-color-scheme`），但使用者一旦 click 就鎖到 light / dark。
- i18n key 縮：刪 `theme.toggle.system` 對應 label；新 key `ui.themeToggle.label`、`ui.themeToggle.toLight`、`ui.themeToggle.toDark`。
- aria-label 必須在 zh-TW + en parity 同時提供。

**Alternatives considered**：
- A: 用 magicui toggler + 額外 `system` reset button — 多按鈕複雜化
- B (採用): 直接捨棄 `system` toggle 入口（fresh load 仍 fallback system）
- C: 不換 toggler — 違反 Sean 在 UI-OVERHAUL-DECISIONS.md 明確指示

### Decision 5: Calendar picker — datetime-local 拆成「date picker + time input」雙欄

shadcnblocks `calendar-standard-3` 是 date-only（含 month nav、week grid、selected highlight）。當前 `meeting-edit-form` 用 `datetime-local`（日期 + 時間混合）。決策：

- `<input type="datetime-local">` → `<Calendar />` (date) + `<Input type="time" />` (time)
- form schema 仍維持 ISO datetime string（合成 `${date}T${time}` 再 parse）
- `meetings/new.tsx` 與 `meeting-edit-form.tsx` 各做兩組（`scheduled_start_at` / `scheduled_end_at`）
- 新增 i18n key: `ui.calendar.openPicker` / `ui.calendar.clear` / `ui.calendar.today`（aria-label）

**Alternatives considered**：
- A: 用 datetime picker（shadcnblocks 另有 datetime block）— 屬 Pro，license 不符
- B (採用): date + time 拆兩欄
- C: 自寫 datetime picker — 違反「不寫多餘元件」原則

### Decision 6: Popover barrel + 既有 callsite 一律走 barrel

當前 `tags/tag-picker.tsx` 直接 `import * as Popover from "@radix-ui/react-popover"`，違反 shadcn barrel 慣例。新增 `packages/web/src/components/ui/popover.tsx`（底層改 animate-ui/base/popover），所有 popover callsite 統一走 barrel：

- `tags/tag-picker.tsx`
- `chunk-action-menu.tsx`（transcript chunk action menu）
- `speaker-color-popover.tsx`
- `transcript-chunk-row.tsx`（含 action popover trigger）

Barrel 內提供：`Popover` / `PopoverTrigger` / `PopoverContent` / `PopoverAnchor`（與 shadcn 命名一致以減少 callsite diff）。

### Decision 7: 全站 hover-info icon button audit + Tooltip 強制掛載

DESIGN.md §4 規定「Tooltip mounted everywhere a hover would reveal supplementary info」。本 change 內含「audit + 補裝」task。Target callsite 至少：

- `recording-badge.tsx` — 30 天到期 hint
- `capture-indicator.tsx` — stream status hint
- `rerun-button.tsx` — 重轉內容說明
- `theme-toggle.tsx` — 切換主題 label
- `locale-toggle.tsx` — 切換語言 label
- 其他 audit task 內列出

新增 i18n key 統一 `ui.tooltip.<topic>` namespace，zh-TW + en parity。

### Decision 8: Test 策略 — smoke + variant + i18n parity

- 每個新 primitive (`popover.tsx` / `progress.tsx` / `loading.tsx` / `calendar.tsx` / `toast-variants.tsx`) 補一個 smoke test in `primitives-smoke.test.tsx` 或對等位置（mount + visible + aria-label 存在）
- 4 個 Toast variant 各自 1 test：呼叫 `toast.info(...)` 後 DOM 出現 `data-type="info"` 且 stripe class 命中
- `meeting-edit-form.test.tsx` 既有測試需更新到 date+time 拆兩欄的 DOM
- `locales.test.ts` deep-equal guard 把關所有新 i18n key

## Implementation Contract

### Behavior contract

1. **Dialog 全站行為一致**：所有開 Dialog（`meeting-link-picker` / `playbook-pane` AlertDialog 區段 / 其他 audit 出來的 callsite）使用 animate-ui dialog motion（scale + fade + blur backdrop 8px）。Dismiss 行為（ESC / backdrop click）不變。
2. **Popover barrel + animate-ui motion**：所有 Popover callsite 改成從 `@/components/ui/popover` 匯入；trigger 在 transcript chunk 與 tag picker 等位置呈現 animate-ui motion（origin-based scale + opacity）。
3. **Tooltip 全站補滿**：任何 icon-only button 或 hover-info button 必須 wrap `<Tooltip>`，content 走 i18n。
4. **Progress (determinate)**：ASR 下載、playbook 產生若可估進度，用 animate-ui progress bar，bar 顏色 `--color-primary`，track 顏色 `--color-surface-2`。
5. **Loading (indeterminate)**：無法估進度時，用 ported `<Loading />`，動畫顏色 `--color-primary`；prefers-reduced-motion 改靜態。
6. **Theme toggler**：右上 toggle 點擊觸發圓形 reveal 動畫（magicui），切 dark↔light；fresh session 仍 fallback system。
7. **Toast 4 variant**：`toast.info(...)` / `.success` / `.warning` / `.error` 在 DOM 上對應 `data-type="info"` 等屬性與 stripe 顏色；既有 `toast(...)` 改為 semantic helper。
8. **Calendar picker**：建立 / 編輯會議的 date 改 shadcnblocks calendar；時間以獨立 `<Input type="time">` 並排；submit 合成 ISO datetime 維持 backend payload 形狀。
9. **i18n parity**：新增 keys 同時進 `zh-TW.json` + `en.json`，`locales.test.ts` deep-equal pass。
10. **License attribution**：uiverse port 在源檔頂端註解標 `Source: https://uiverse.io/gustavofusco/rare-pug-90 (CC0)`；shadcnblocks 在源檔註解標 `Source: https://www.shadcnblocks.com/component/calendar/calendar-standard-3`。

### Data shapes

```typescript
// toast-variants.tsx
type ToastVariant = "info" | "success" | "warning" | "error";

interface SemanticToastOptions {
  description?: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

// sonner.tsx 暴露的延伸 (vs 既有 raw toast)
declare const toast: {
  (msg: string): void; // legacy passthrough
  info(msg: string, opt?: SemanticToastOptions): void;
  success(msg: string, opt?: SemanticToastOptions): void;
  warning(msg: string, opt?: SemanticToastOptions): void;
  error(msg: string, opt?: SemanticToastOptions): void;
};

// loading.tsx
interface LoadingProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  "aria-label": string; // 強制
}

// calendar.tsx
interface CalendarPickerProps {
  value?: Date;
  onChange: (next: Date) => void;
  min?: Date;
  max?: Date;
  className?: string;
}

// i18n new keys (excerpt) — zh-TW + en parity
{
  "ui": {
    "toast": {
      "info":    { "label": "資訊"   /* en: "Info"    */ },
      "success": { "label": "完成"   /* en: "Done"    */ },
      "warning": { "label": "注意"   /* en: "Warning" */ },
      "error":   { "label": "錯誤"   /* en: "Error"   */ }
    },
    "themeToggle": {
      "label":    "切換主題",
      "toLight":  "切到淺色",
      "toDark":   "切到深色"
    },
    "calendar": {
      "openPicker": "開啟日期選擇器",
      "clear":      "清除日期",
      "today":      "今天"
    },
    "tooltip": {
      "recording":         "30 天後自動刪除",
      "capture":           "雙聲道擷取中",
      "rerun":             "重新轉錄",
      "themeToggle":       "切換主題",
      "localeToggle":      "切換語言"
    }
  }
}
```

### Failure modes

- **vendor CLI install 失敗 / peer dep 衝突** → Task 0 spike 必須早期偵測；偵測到衝突回報 Sean，本 change 暫停而非繼續硬上
- **shadcnblocks `calendar-standard-3` 屬 Pro / license 不符** → Task 0 偵測後改用 shadcn 內建 `calendar` 元件作 fallback（但目前 `components/ui/` 無，須補）並回報 Sean
- **uiverse port 動畫在 prefers-reduced-motion 環境壞掉** → Loading 強制 `@media (prefers-reduced-motion: reduce)` fallback 為靜態 dot 或 Skeleton
- **既有 toast callsite 漏改 semantic helper** → `toast(...)` 暫保 legacy passthrough 行為，避免 build break；codemod 或人工 sweep 列為任務驗收項
- **animate-ui dialog motion 干擾 e2e selector** → e2e 仍以 `data-testid` 為主，不依賴 motion timing；如有 timing race 需在 test 用 `findBy*` 等待

### Acceptance criteria

- **Task 0 spike** 結束時：vendor install 成功 + token override 生效 + build / tsc / dev server 三項綠
- **change 結束時**：
  - `bun run test` 整體 pass，新增 smoke test 全綠
  - `bunx tsc --noEmit` 0 error
  - `bunx oxlint` 0 error
  - `locales.test.ts` parity pass
  - 全站 Dialog / Popover / Tooltip / Progress / Loading / Theme toggler / Calendar / Toast 視覺對齊 DESIGN.md §4
  - 人工 walkthrough 確認 prefers-reduced-motion 時所有動畫退化為靜態
- **License audit**：uiverse / shadcnblocks 源檔頂端註解標 source URL；PR 內附 attribution 表

### Scope boundaries (in / out)

**In scope:**

- `packages/web/src/components/ui/` 內列出的 5 個新檔 + 4 個修改檔
- `packages/web/src/components/theme-toggle.tsx`
- `packages/web/src/components/meeting-edit-form.tsx`
- `packages/web/src/routes/meetings/new.tsx`
- 所有 Dialog / Popover 既有 callsite 的 import 改 barrel
- 全站 `toast(...)` callsite 改 semantic helper
- 全站 hover-info icon button audit + Tooltip 補裝
- `packages/web/src/locales/zh-TW.json` + `packages/web/src/locales/en.json` 新增 keys
- `packages/web/package.json` 新依賴
- `packages/web/src/components/ui/primitives-smoke.test.tsx` 新增測試
- ui-design-system delta spec

**Out of scope:**

- Backend / Auth gateway / DB
- P3 effect-layer 元件
- P4 routing / IA refactor
- P5 meeting detail layout
- `openspec/changes/single-channel-recording-entry/`
- domain-specific 元件 (TranscriptChunk / CaptureIndicator / Pane 等) 本體邏輯
- e2e / Playwright 改寫（測試 selectors 保留）
- 新 ADR（如 vendor 選擇有方向性決策需開 ADR 由 Sean 拍板）

## Risks / Trade-offs

- **[animate-ui CLI install 跟現有 shadcn / radix 衝突]** → Task 0 spike 在試驗分支試裝；發現衝突回報 Sean
- **[shadcnblocks `calendar-standard-3` license 或位於 Pro tier]** → Task 0 仔細看 page license header；發現 Pro fallback 用 shadcn 內建 calendar，但需在 task 內補
- **[uiverse port 後配色錯誤 / 動畫不順]** → 端到端 visual check + reduced-motion fallback
- **[全站 hover-info audit 漏項]** → audit 任務獨立列為一個 task，附 component list，PR 審查時必須勾完
- **[8+ 處 sonner 既有 callsite 換 semantic helper 漏改]** → `toast(...)` 暫保 legacy passthrough；人工 sweep + grep PR 驗證
- **[meeting-edit-form datetime-local 拆兩欄影響既有 e2e]** → test 改 query `getByLabelText("date")` + `getByLabelText("time")`，selectors 不依賴 input type

## Migration Plan

1. Task 0 spike（試驗分支）→ green light or 回報
2. P1 (`ui-overhaul-aura-tokens`) 必須先 merge — 本 change 開工前確認 `--color-info` / `--color-success` / `--color-warning` / `--color-danger` / `--color-me` / `--color-them` 存在於 `index.css`
3. Task 順序：新增 5 個 primitive 檔（含測試）→ 重寫 dialog / tooltip / sonner 底層 → theme-toggle 換 magicui → calendar form 拆兩欄 → callsite sweep（toast / popover / tooltip audit）→ i18n parity → spec delta + tasks 最後 sweep
4. Rollback：本 change 全在 frontend，rollback 回 P1 即可；無 DB migration、無 API contract 改動

## Open Questions

- Task 0 spike 完成後若 animate-ui / magicui 之一 install 失敗，是否退回到自寫 motion + 既有 radix tooltip / dialog？（需 Sean 拍板）
- shadcnblocks `calendar-standard-3` 若為 Pro tier，是否改用 `shadcn add calendar` 內建版？或暫不換、留現 datetime-local？
- Theme toggler 捨棄 `system` 三段 UI 入口後，是否在 settings page 補一個「跟隨系統」開關？本 change 預設不加，留 P4 settings 重整時再評估
