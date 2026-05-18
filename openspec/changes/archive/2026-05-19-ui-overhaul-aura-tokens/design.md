## Context

DESIGN.md（2026-05-18 鎖定）是專案 design system 的 single source of truth，把目前的 `ui-overhaul-claude-design`（light primary-hue 280 / dark primary-hue 50）整體換錨到 [Aura by Dalton Menezes](https://github.com/daltonmenezes/aura-theme)。

現行 `packages/web/src/index.css` 用 `--primary-hue` / `--primary-hue-dark` 兩個 knob 把所有 colour token 用 oklch 串接，light=violet 280、dark=orange 50。Aura 換錨後：

- **兩個 theme 的 primary 都在 violet 家族**：dark 用 vibrant Aura Purple `#A277FF`（hue ≈ 290），light 用 soft Aura Violet `#8464C6`（hue ≈ 290）。`--primary-hue` knob 結構保留以供 design-canvas 微調，但兩個 theme 的預設值都改成 290。
- **Accent 從 primary alias 拆出來變成獨立 magenta**：dark Magenta Bloom `#F694FF`、light Mauve Soft `#C17AC8`。
- **Speaker 顏色不再透過 `--primary-hue` 衍生**：me 直接寫死 blue（hue 220），them 直接寫死 magenta（hue 320），跟 primary 解耦，符合 DESIGN.md「色票語義是 invariant across modes」鐵律。
- **Radius 改 sharp**：4 / 6 / 8 / 12（DESIGN.md `rounded` 跟 Sean 答 B3）。
- **Shadow**：dark 幾乎無，light 留淡。
- **新增 `--color-info` semantic**：Toast 4 變體需要。
- **不重寫 Sonner 元件**：只透過 `<Toaster>` 的 `toastOptions.classNames` / inline style 將 4 個變體（info / success / warning / error）對應到 token；P2 才換成 animate-ui Toaster。

P2-P5 已被 DESIGN.md §6 Roadmap 鎖定，本 change 嚴格不跨界。

## Goals / Non-Goals

**Goals:**

- 把 `packages/web/src/index.css` 換成 DESIGN.md §2 / §3 / §4（限定 radius+shadow+toast）token mapping。
- me/them 配色從 primary-hue 衍生改成寫死 blue/magenta，直接在 `index.css` token level 完成；任何透過 `var(--color-me*)` / `var(--color-them*)` 引用的元件視覺自動跟進。
- Toast 4 變體（info-blue / success-green / warning-orange / error-red）只在 token + Sonner prop 層完成色票對齊，**不換** Toaster 元件本身。
- 新增 oklch validation smoke test，防止後續 PR 偷渡 raw hex 或 dark/light parity drift。
- 移除 `recording-badge` 的 hex fallback；其他 hardcoded 色（Google brand SVG、`tag-palette` 9 色 swatch、`border-beam` mask `#000`）逐一裁決保留或修。

**Non-Goals:**

- 不換 Dialog / Popover / Tooltip / Progress / Toast 元件邏輯（P2）。
- 不加 Stars background / animated-list / bar-visualizer / glass-dock / 任何 magicui / uiverse 效果元件（P3）。
- 不動 routing / IA（P4）。
- 不動 Meeting detail 排版（P5）。
- 不動 typography token、`--space-*`、`--text-*`、density variants。
- 不動 backend、DB schema、API。
- 不動 locale 檔（無新 user-visible string）。
- 不動 `tag-palette.ts`（隔離域）、Google brand SVG fill（brand asset）。

## Decisions

### D1. Token block 整段重寫，保留 `--primary-hue` knob 結構

不嘗試在 `--primary-hue` 上換 hue 把 Aura mapping 用 knob 表達。DESIGN.md §2 把 colour 跟 role 綁死成 invariant（me=blue / them=magenta / success=green / warning=orange / danger=red / info=blue / accent=magenta），這些角色的 hue 跟 primary 解耦才能成立。

- **保留** `--primary-hue` / `--primary-hue-dark` 兩個變數（design-canvas 仍可拉），但兩個 theme 預設值都改成 290（violet）。
- **保留** `[data-density]` / `[data-radius]` / `[data-transcript-contrast]` 三個 knob block 結構，但：
  - `[data-radius="sharp"]` 跟新 base 一致或更銳（base=4/6/8/12，sharp 變體=2/4/6/8）。
  - `[data-radius="soft"]` 跟舊一致（6/12/16/20）。
- **重寫**所有 `--color-*` 值為 DESIGN.md §2 列出的 oklch 近似值（hex 經 oklch 對照表轉換，DESIGN.md 已給出）。

**Alternatives considered**:

- (A) 把 me/them/accent 用 `--primary-hue` 衍生（現行做法）—— rejected：跟 DESIGN.md「色票語義 invariant」相違，且 dark/light 換 hue 後 me/them 視覺會跟著飄。
- (B) 整段 `index.css` 砍掉重寫，連 `--primary-hue` knob 都拿掉—— rejected：design-canvas 元件還在用，且未來其他 theme 仍可能用到；保留結構不傷成本。

### D2. me=blue / them=magenta 寫死 oklch，與 primary 解耦

DESIGN.md §2 + Sean 答 B1=a 一起鎖定：

- **dark me**: `oklch(0.86 0.12 220)` ≈ Glacier Blue `#82E2FF`
- **dark me-soft**: `oklch(0.32 0.06 220)`（用 DESIGN.md `info-soft`/`me-soft` 等價灰藍）
- **light me**: `oklch(0.65 0.10 220)` ≈ Steel Blue `#6CB2C7`
- **light me-soft**: `oklch(0.92 0.04 220)` ≈ `#DDEDF2`
- **dark them**: `oklch(0.77 0.22 320)` ≈ Magenta Bloom `#F694FF`
- **dark them-soft**: `oklch(0.36 0.10 320)` ≈ DESIGN.md `primary-soft` 同層
- **light them**: `oklch(0.55 0.15 320)` ≈ Mauve Soft `#C17AC8`
- **light them-soft**: `oklch(0.90 0.05 320)`

`color-mix(in oklch, var(--color-me-soft) calc(var(--me-tint-alpha) * 1000%), transparent)` 的算式不動—— `transcript-color-schemes.ts` 的 me/counterparty branch 純 token-driven，token 換色就跟進，無需改 logic。

**Alternatives considered**:

- (A) me 用 light primary purple、them 用 dark primary orange—— rejected：跟 DESIGN.md 鎖定不符。
- (B) me/them 仍掛在 `--primary-hue` 但 offset—— rejected：design-canvas 換 hue 會把 me/them 整個飄走。

### D3. Radius 改 sharp 4/6/8/12，knob 變體保留

DESIGN.md `rounded` + Sean 答 B3：

- **base**: `--radius-sm: 4px` / `--radius-md: 6px` / `--radius-lg: 8px` / `--radius-xl: 12px` / `--radius-pill: 999px`
- **`[data-radius="sharp"]`**: `2px` / `4px` / `6px` / `8px`（再銳一階）
- **`[data-radius="soft"]`**: `6px` / `12px` / `16px` / `20px`（保留 escape hatch）

**Alternatives considered**:

- (A) base 改 4/8/12，sharp 變體 4/6/8—— rejected：跟 DESIGN.md `rounded` 字面值不對齊。

### D4. Shadow：dark 改 inset hairline / light 維持淡 drop

DESIGN.md `shadow.dark` / `shadow.light`：

- **dark**:
  - `--shadow-sm: none`
  - `--shadow-md: 0 1px 0 rgba(0,0,0,0.3) inset`
  - `--shadow-lg: 0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.4)`
- **light**: 保留現行近似值，微調對齊 DESIGN.md
  - `--shadow-sm: 0 1px 2px rgba(20,14,40,0.04)`
  - `--shadow-md: 0 4px 16px rgba(20,14,40,0.06), 0 1px 3px rgba(20,14,40,0.04)`
  - `--shadow-lg: 0 12px 32px rgba(20,14,40,0.1), 0 2px 6px rgba(20,14,40,0.06)`
- `--shadow-focus` 保留 oklch primary 25% 環。

`rgba()` 在 shadow 裡是 oklch 替代品的合理例外（CSS shadow spec 對 oklch 支援度不全），於 design.md 顯式裁決。

**Alternatives considered**:

- (A) dark 完全無 shadow—— rejected：inset hairline 對 card 邊界仍有幫助。

### D5. `--color-accent` 從 primary alias 拆出來變成獨立 magenta

DESIGN.md §2：accent = Magenta Bloom（dark）/ Mauve Soft（light）。

- **dark**: `--color-accent: oklch(0.77 0.22 320)` / `--color-accent-foreground: oklch(0.14 0.012 290)`
- **light**: `--color-accent: oklch(0.55 0.15 320)` / `--color-accent-foreground: oklch(1 0 0)`

所有 `bg-(--color-accent)` / `text-(--color-accent)` 引用會自動變 magenta；視覺變化是 P1 期望，**不算 regression**。

**Trace check**: grep `--color-accent` 在 `packages/web/src/**/*.{tsx,ts}` 找出影響範圍，design.md 內列出（task 拆解時要逐一視覺驗證）。

### D6. 新增 `--color-info` / `--color-info-soft` semantic

Toast 4 變體需要 info-blue 跟 me/them 解耦。DESIGN.md §2 給的值：

- **dark info**: `oklch(0.86 0.12 220)`（跟 me 同色，DESIGN.md §2 明確說 me 就是 info）
- **dark info-soft**: `oklch(0.32 0.06 220)`
- **light info**: `oklch(0.65 0.10 220)`
- **light info-soft**: `oklch(0.92 0.04 220)`

Info token 跟 me token **值相同但獨立宣告**，因為 me 是 speaker 語義、info 是 status 語義；未來如果 me 配色要再調，info 不會跟著動。

### D7. Sonner Toaster 4 變體：透過 CSS data-attr selector 對齊 token

`packages/web/src/components/ui/sonner.tsx` 目前是 shadcn 預設配置。本 change 不動 Toaster JSX 結構或 motion，只在 `index.css` 加 CSS selector：

```
[data-sonner-toast][data-type="success"] {
  --normal-bg: var(--color-success-soft);
  --normal-border: var(--color-success);
  --normal-text: var(--color-foreground);
}
/* 同樣 pattern for error/warning/info */
```

兩條路都不重寫元件邏輯。**Decision: 採 CSS-only**—— 不動 React 元件、跟 P2 換 Toaster 不衝突。

**Alternatives considered**:

- 直接換 animate-ui Toaster—— rejected：P2 scope，不在本 change。
- 用 `richColors` prop—— rejected：色票被 Sonner 內建鎖定，無法套 Aura token。
- 在 `<Toaster toastOptions={{ classNames }}>` 加 class —— rejected：Sonner 內部把 `--normal-bg` 寫成 inline style，會覆蓋 className 的 bg。CSS variable override 才穩。

### D8. `recording-badge` hex fallback 移除

`packages/web/src/components/recording-badge.tsx` 的 `bg-(--color-success, #22c55e)` 是 Tailwind v4 arbitrary value 的 CSS variable fallback 語法。但 `--color-success` 是 design token 一定會在，hex fallback 是冗餘，且違反 DESIGN.md「無 raw hex in component class strings」。

**Decision**: 改成 `bg-(--color-success)`，移除 hex fallback。

### D9. `border-beam.tsx` mask `#000` 視為合規例外

`packages/web/src/components/magicui/border-beam.tsx` 的 `WebkitMask: "linear-gradient(#000 0 0) content-box, ..."` 是 CSS mask 語法，`#000` 在這裡是 mask alpha（不是視覺色），oklch 在 mask context 支援度差。

**Decision**: 列入 oklch validation test 的 allowlist（component-level mask context），保留 `#000`。

### D10. oklch validation smoke test

新增 `packages/web/src/lib/tokens.test.ts`（或 `__tests__/tokens.test.ts` 視 repo 慣例）：

1. 讀 `packages/web/src/index.css` 純文字。
2. 對 `--color-*` 行斷言：值必為 `oklch(...)` / `var(--color-*)` / `var(--color-* / <alpha>)` 之一。
3. dark / light parity：兩個 theme block 內宣告的 `--color-*` 變數 key 集合必須相同（symmetric difference = 空）。
4. 對 `packages/web/src/**/*.{tsx,ts}`（排除 `**/*.test.*`、`magicui/border-beam.tsx` mask context、`tag-palette.ts`、Google brand SVG）grep `#[0-9a-fA-F]{3,8}` 跟 `rgb(` / `rgba(`，違規 → 測試 fail。

allowlist 用顯式陣列 + 註解寫明原因，未來新加例外要附 justification。

### D11. Transcript / Advisor / 其他 me-them consumer 視覺驗證

token 換色後元件 logic 不動，但要逐一視覺確認新藍/粉色渲染正確：

- `transcript-pane.tsx`（accent + chunk row border / background）
- `transcript-chunk-row.tsx`（chunk row 渲染）
- `speaker-color-popover.tsx`（如有 me/them swatch 直接渲染）
- `advisor-pane.tsx`（如有 bubble tint 依 speaker）

任務拆解時各自一個 sub-task：**讀**該檔案、確認是純 `var(--color-me*)` / `var(--color-them*)` token 引用、無 hardcoded primary-hue 衍生算式；若發現有，改成 token 引用（無 logic 改動）。

## Implementation Contract

**Observable behavior after this change ships**:

1. 啟動本機開發環境後，dark theme 預設背景變成略紫近黑 `oklch(0.17 0.015 290)`，primary 按鈕變 Aura Purple `oklch(0.65 0.22 290)`。
2. Light theme 預設背景變成 mist bone `oklch(0.97 0.003 295)`，primary 按鈕變 Aura Violet Soft `oklch(0.50 0.18 290)`。
3. 任何 transcript chunk 標 `me` 的 row → 藍色 accent / 淡藍背景；標 `counterparty` → 粉色 accent / 淡粉背景。dark/light 都成立。
4. 任何 `bg-(--color-accent)` 元件在 dark 變 magenta、light 變 mauve（**不再** = primary purple）。
5. `toast.success("X")` → 綠色（success）；`toast.error("X")` → 紅色（danger）；`toast.warning("X")` → 橘色（warning）；`toast.info("X")` → 藍色（info）。Toaster 元件 JSX / motion 不變。
6. 按鈕 / card / dialog 圓角從 8/12/16 變成 4/6/8。
7. Dark mode card 不再有明顯 drop shadow（改 inset hairline）；light mode 維持淡 drop shadow。

**Acceptance criteria**:

- `bun --filter @meeting-playbook/web test` 全綠，含新加的 `tokens.test.ts` 與既有 `transcript-color-schemes.test.ts` 補測。
- `oxlint` / `oxfmt` 無 warning。
- `bun --filter @meeting-playbook/web build` 成功。
- 視覺迴歸：在 dark + light 兩個 theme 各看一次 `/meetings/list`、`/meetings/:id`（含 transcript + advisor pane）、`/settings/profile`，色票對齊 DESIGN.md §2。
- `spectra validate ui-overhaul-aura-tokens` 過。
- `spectra analyze ui-overhaul-aura-tokens --json` 無 Critical / Warning。

**Scope boundaries**:

- **In**: `packages/web/src/index.css`、`packages/web/src/components/recording-badge.tsx`、`packages/web/src/components/ui/sonner.tsx`、`packages/web/src/lib/transcript-color-schemes.ts`（測試補）、新檔 `packages/web/src/lib/tokens.test.ts`、以及 me/them token consumer 的視覺驗證（無 logic 改動）。
- **Out**: 任何 Dialog / Popover / Tooltip / Progress / Toaster 元件邏輯改動、任何 magicui / uiverse 動畫元件、任何 routing 或 IA 改動、Meeting detail 排版、backend、locale 檔。

**Interface / data shape**: 純 CSS variable 換值 + 新增 4 個 token（`--color-info`、`--color-info-soft`、`--color-accent` 從 alias 變獨立、`--color-them` 從 hue-280 變 hue-320）。無 TS / JS API 改動。

**Failure modes**:

- 換 token 後對比度跌破 WCAG AA → 視覺驗證 + 對 DESIGN.md §2 「WCAG contrast notes」對齊（已 pre-computed）。
- Sonner CSS selector 在 v3 / v4 升級時失效 → 註解寫死 selector 來源，未來 Sonner upgrade 一併處理。
- oklch test 誤判 `tag-palette.ts` / `border-beam.tsx` → allowlist 顯式列出。

## Risks / Trade-offs

- **[Risk]** 視覺迴歸面大，每個依賴 me/them/accent/primary 的元件都會變色。
  → **Mitigation**: 對 transcript / advisor / meeting-card 既有 snapshot test 更新 baseline；視覺對比走 DESIGN.md §2 對比度表。
- **[Risk]** `--color-accent` 從 primary alias 拆出來變 magenta，有元件可能本來預期 accent = primary。
  → **Mitigation**: 在 task 拆解時逐一 grep `--color-accent` 用法，視覺驗證（非 logic 改）。
- **[Risk]** Sonner CSS selector hack 跟 Sonner 內部實作耦合，升版可能壞。
  → **Mitigation**: 註解寫明 selector 來源（Sonner data attr），P2 換 Toaster 時一起重寫。
- **[Risk]** oklch test 對 `index.css` 內容做 regex 比對，未來新加 token 格式可能誤判。
  → **Mitigation**: regex 寬鬆，僅斷言「值以 `oklch(` / `var(` / `none` / `transparent` 開頭」。
- **[Trade-off]** `--primary-hue` knob 結構保留但兩個 theme 都用 290，knob 在實務上只能微調 hue 不能切 theme—— 是 P1 期望，design-canvas 仍能用。

## Migration Plan

- 純前端 token 換色，**無 DB migration、無 API 變更、無 env var 新增**。
- 部署：commit + 推上 dev branch → 本機 dev server 跑起來驗 dark/light 雙 theme 各 3 個關鍵頁 → 通過後 PR。
- Rollback：純 `git revert` `packages/web/src/index.css` 跟 4 個元件檔即可。

## Open Questions

無。Sean 已在 UI-OVERHAUL-DECISIONS.md 把所有 P1 相關決策（B1 / B2 / B3 / B4）拍板，DESIGN.md §2 / §3 / §4（限定 P1 範圍）為 single source of truth。
