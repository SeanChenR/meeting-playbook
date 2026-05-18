## Why

DESIGN.md（2026-05-18 由 Sean 與 UI-OVERHAUL-DECISIONS.md 一起鎖定）把專案 design system 從現行的 `ui-overhaul-claude-design`（light=紫羅蘭 280 / dark=暖橘 50）整體換錨到 [Aura by Dalton Menezes](https://github.com/daltonmenezes/aura-theme)：dark 為主、light 用 `*-soft` 變體鏡像、me=blue / them=pink、sharp 4/6/8 radius、dark 幾乎無 shadow / light 留淡 shadow。為了 PR 可審、變更可回滾，這個改版拆成 5 段（DESIGN.md §6 Roadmap），P1 就是只動 **token 層 + 直接消費 me/them tokens 的元件 colour bindings**，完全不碰元件 logic、layout、routing、IA。

## What Changes

- **MODIFY** `packages/web/src/index.css` 的 `:root` / `[data-theme="light"]` / `[data-theme="dark"]` token block：整段換成 DESIGN.md §2 的 Aura colour mapping（dark 用 vibrant 原色，light 用 `*-soft` 鏡像），新增 `--color-info` / `--color-info-soft` 兩個 semantic token，並把 `--color-accent` 從目前的 `var(--color-primary)` alias 拆出來變成獨立的 magenta-bloom（dark）/ mauve-soft（light）色。
- **MODIFY** `--color-me` / `--color-me-soft` / `--color-them` / `--color-them-soft`：me 改 Glacier Blue（dark `#82E2FF` ≈ `oklch(0.86 0.12 220)`，light Steel Blue `#6CB2C7` ≈ `oklch(0.65 0.10 220)`），them 改 Magenta Bloom（dark `#F694FF` ≈ `oklch(0.77 0.22 320)`，light Mauve Soft `#C17AC8` ≈ `oklch(0.55 0.15 320)`）— 直接用 oklch，不再透過 `--primary-hue` 串接。
- **MODIFY** `--radius-*` 預設值：sharp 4 / 6 / 8 / 12（沿用 DESIGN.md `rounded` 與 Sean 答 B3）。`[data-radius="sharp"]` / `[data-radius="soft"]` knob 保留結構但 base 值換成 sharp。
- **MODIFY** `--shadow-sm/md/lg`：dark 改成 DESIGN.md `shadow.dark`（`sm: none`、`md` inset hairline、`lg` 1px ring + 24px drop）；light 保留現行淡 shadow（DESIGN.md `shadow.light` 跟現行幾乎相同，僅微調 token 值對齊）。
- **MODIFY** `packages/web/src/components/transcript-pane.tsx` 第 131 / 293-304 行：`accent` 跟 inline style 從 `--color-them` 引用維持不變（token 換色後自動跟著新色），但要把 hardcoded `borderLeft: "3px solid var(--color-them)"` 用法改成 token-consistent class 或保持 inline 但確保 dark/light 都讀到新 token；加 visual regression（screenshot diff 或 snapshot test）確認 magenta bloom 真的渲染出來。
- **MODIFY** `packages/web/src/components/recording-badge.tsx:33` 的 hex fallback `bg-(--color-success, #22c55e)` → 移除 hex fallback（success token 必存在）或改成 `oklch()` 等價值。
- **MODIFY** `packages/web/src/lib/transcript-color-schemes.ts` 的 `_resolveClusterColor`：me/counterparty 兩個 branch 已經透過 `--color-me*` / `--color-them*` token 引用，無需改 logic；補一個 unit test 驗證 token 換色後 `_resolveClusterColor("me", ...)` 回傳的 accent 字串仍解析成新的藍色 hue（220 而非 `--primary-hue`）。
- **MODIFY** Sonner toast 設定（`packages/web/src/components/ui/sonner.tsx`）：透過 `richColors` + CSS 變數對應，產出 4 個 semantic 變體的視覺—— info=`--color-info`、success=`--color-success`、warning=`--color-warning`、error=`--color-danger`。不重寫 Toaster 元件（那是 P2 的事），只在 token 層 + Toaster prop / className overrides 完成色票對齊。
- **ADD** `packages/web/src/index.css` 或 `packages/web/src/lib/__tests__/tokens.test.ts`：oklch validation smoke test，掃 `index.css` 確認所有 `--color-*` 變數都是 `oklch(...)` 格式、無 raw hex、雙 theme block 鍵集合相同（dark / light parity）。
- **CHORE** repo-wide grep `packages/web/src/**/*.{ts,tsx}` 找剩餘 hardcoded `#xxxxxx` / `rgb(` / `rgba(`：保留品牌 Google logo SVG fill（`#4285F4` 等，brand asset，不歸 token system 管）跟 `tag-palette.ts`（已隔離為獨立 palette），其餘違規（如 `recording-badge` 的 hex fallback、`border-beam` 的 mask hex）逐一處理或在 design.md 裡解釋為什麼放行。

## Non-Goals

- **不換** Dialog / Popover / Tooltip / Progress / Toast 元件本身（只動 token / className，不重寫元件邏輯或 motion）— P2 `ui-overhaul-primitive-upgrade`。
- **不加** Stars background / animated-list / bar-visualizer / glass-dock / 任何 magicui / uiverse 動畫元件 — P3 `ui-overhaul-animated-surfaces`。
- **不動** routing、navigation：`/calendar/upcoming` 不砍、`/recordings` 不加 — P4 `ui-overhaul-ia-refactor`。
- **不動** Meeting detail 排版（三選一 deferred） — P5。
- **不動** `openspec/changes/single-channel-recording-entry/` 或 S27 相關檔。
- **不動** backend / DB schema / API。`recording.stream` enum 維持 `'me'` / `'counterparty'`，UI 端的 `me` / `counterparty` 字面值不變（只是視覺色從 hue-280-derived 換成 hue-220 blue）。
- **不動** locale 檔（無新 user-visible string）— 但若 oklch validation test 報錯訊息算 user-visible（dev 工具不算），不算 i18n debt。
- **不動** typography token、`--space-*`、`--text-*`、density variants — 已被 DESIGN.md §3 認可不動。
- **不換** `tag-palette.ts` 的 9 色 swatch 跟 Google brand SVG hex — 隔離域，不歸 design token 管。
- **不動** `--primary-hue` / `--primary-hue-dark` knob 結構 — 換錨之後 primary 在兩個 theme 都是 violet，knob 仍可微調但預設值改成 dark=290 / light=290。

## Capabilities

### Modified Capabilities

- `ui-design-system`: 設計 token 的色相錨點、me/them 顏色語義、radius 預設值、shadow 預設、`--color-accent` 是否與 primary 同色、是否新增 `--color-info` semantic、Toast 4 變體色彩對應—都是 spec 層級的行為變更，不是純實作細節。

## Impact

**Affected code (frontend only)**:
- `packages/web/src/index.css` — token block 整段重寫
- `packages/web/src/components/transcript-pane.tsx` — 視覺驗證（無 logic 改動）
- `packages/web/src/components/recording-badge.tsx` — 移除 hex fallback
- `packages/web/src/components/ui/sonner.tsx` — 4 個 toast 變體色彩對應（class / prop overrides only）
- `packages/web/src/lib/transcript-color-schemes.ts` — 補測試（無 logic 改動）
- `packages/web/src/components/magicui/border-beam.tsx` — 評估 mask 用 `#000` 是否標記為合規例外

**Spec deltas**:
- `openspec/specs/ui-design-system/spec.md` — MODIFIED requirements：色相錨點 / me-them 配色 / radius 預設 / shadow 預設 / accent 獨立 / info token / Toast 4 變體；新增 oklch validation smoke test scenario。

**i18n**: 無新 user-visible string。若有的話兩個 locale 都會動（CLAUDE.md i18n parity 規矩）。

**Tests**:
- 新增 `packages/web/src/lib/__tests__/tokens.test.ts`（或同義位置）oklch validation
- 補 `transcript-color-schemes.test.ts` me/them branch 的新色斷言（hue 220 / 320）
- 既有 visual snapshot（transcript-pane / advisor / meeting-card）需要 baseline 更新

**Risk**:
- 視覺迴歸大，但純色票替換、無 layout / logic 動，PR review focus 在色票對齊 + 對比度 (WCAG AA on primary purple ≈ 4.8-5.8:1，DESIGN.md §2 已驗)。
- `--color-accent` 從 alias 變成獨立色：所有 `bg-(--color-accent)` / `text-(--color-accent)` 引用會從 violet 變成 magenta — 是 P1 期望的視覺變化，不算 regression。
- Speaker me/them 換色：跟 transcript / advisor 任何依賴「me=偏紫」的視覺記憶會中斷，但 ADR-0028 跟 DESIGN.md §2 已把藍/粉色綁進 domain glossary，沒退路。

**Deps**: 無新 npm / pip / env var。
