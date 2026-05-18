<!--
P1 of 4 — pure token-layer replacement per DESIGN.md §2/§3/§4.
Each task delivers an observable behavior + a verification target.
Order: failing test scaffold → token rewrite → consumer visual audit → toast variants → final validate/build.
-->

## 1. 測試底盤先架好（D10 oklch validation smoke test）

- [x] 1.1 寫 `packages/web/src/lib/tokens.test.ts` 的測試骨架（紅燈）：直接覆蓋 "oklch validation smoke test SHALL guard token format and dark/light parity" 需求—— 讀 `packages/web/src/index.css`、對所有 `--color-*` 值做 regex 斷言、檢查 dark/light parity、檢查 `**/*.{ts,tsx}` 無未授權 raw hex / rgb / rgba。此刻所有斷言都會 fail（現行 `index.css` 缺 `--color-info` 等 token）；驗證：`bun --filter @meeting-playbook/web test tokens` 出現預期失敗清單 ≥ 3 條。

- [x] 1.2 在同個測試檔加 allowlist 對應 "`border-beam.tsx` mask `#000` 視為合規例外" 決策：`tag-palette.ts`、`magicui/border-beam.tsx`、`routes/login.tsx`、`routes/settings/profile.tsx`、`recording-badge.tsx`（會被 5.1 移除）每個都附 inline 註解寫明 justification。驗證：手動 review allowlist 註解 ≥ 4 行，每個 entry 有 `// reason:` 開頭。

## 2. Token block 整段重寫，保留 `--primary-hue` knob 結構（D1）

- [x] 2.1 把 `packages/web/src/index.css` 的 `:root` / `[data-theme="light"]` block 換成 Aura `*-soft` mapping：背景 `oklch(0.97 0.003 295)`、`--color-primary: oklch(0.50 0.18 290)`、`--primary-hue` 預設 290（執行「token block 整段重寫，保留 `--primary-hue` knob 結構」決策的 light 半邊）。覆蓋 "Design tokens SHALL be expressed as oklch-based CSS variables across two themes" 的 light theme scenario。驗證：`bun --filter @meeting-playbook/web test tokens` 中 light theme parity 段轉綠；視覺檢查 login page 在 light theme 變成 mist bone 底 + soft violet 按鈕。

- [x] 2.2 把 `[data-theme="dark"]` block 換成 Aura vibrant mapping：背景 `oklch(0.17 0.015 290)` (Ink Violet)、`--color-primary: oklch(0.65 0.22 290)` (Aura Purple)、`--primary-hue-dark` 預設 290（完成「token block 整段重寫，保留 `--primary-hue` knob 結構」的 dark 半邊）。覆蓋 "Design tokens SHALL be expressed as oklch-based CSS variables across two themes" 的 dark theme scenario。驗證：tokens 測試 dark theme scenario 轉綠；視覺檢查 login page 在 dark theme 是略紫近黑 + vibrant violet 按鈕。

- [x] 2.3 執行「me=blue / them=magenta 寫死 oklch，與 primary 解耦」決策：把 `--color-me` / `--color-me-soft` / `--color-them` / `--color-them-soft` 改寫成直接的 oklch 值（hue 220 blue / hue 320 magenta），不再透過 `--primary-hue` 衍生。覆蓋 "TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline" 的「speaker tokens are independent of primary hue」scenario。驗證：在瀏覽器 console 跑 `getComputedStyle(document.documentElement).getPropertyValue('--color-me')`，dark 回 `oklch(0.86 0.12 220)`、light 回 `oklch(0.65 0.10 220)`。

- [x] 2.4 執行「`--color-accent` 從 primary alias 拆出來變成獨立 magenta」決策：dark 設 `oklch(0.77 0.22 320)`、light 設 `oklch(0.55 0.15 320)`，移除舊有 `var(--color-primary)` 綁定。覆蓋 "`--color-accent` SHALL be an independent magenta token, not a primary alias" 的兩個 scenario。驗證：在 dev page 放一個 `<div className="bg-(--color-accent)">` 視覺確認 dark=magenta、light=mauve，且明顯不同於 primary purple。

- [x] 2.5 執行「新增 `--color-info` / `--color-info-soft` semantic」決策：在兩個 theme block 加 token（值同 `--color-me` 但獨立宣告）。覆蓋 "`--color-info` SHALL be a distinct status token decoupled from speaker me" 的「info token declared independently from me token」scenario。驗證：tokens 測試裡新增的「info 跟 me 各自獨立宣告」斷言轉綠。

- [x] 2.6 執行「radius 改 sharp 4/6/8/12，knob 變體保留」決策：把 `--radius-sm/md/lg/xl` 預設值改成 sharp `4 / 6 / 8 / 12`，並把 `[data-radius="sharp"]` 變體調成更銳的 `2 / 4 / 6 / 8`，`[data-radius="soft"]` 保留舊值。覆蓋 "Default radius scale SHALL be sharp 4 / 6 / 8 / 12" 兩個 scenario。驗證：視覺檢查 `/meetings/list` 上的卡片角從 12px → 8px、按鈕角從 8px → 4px。

- [x] 2.7 執行「shadow：dark 改 inset hairline / light 維持淡 drop」決策：把 `--shadow-sm/md/lg` dark 換成 DESIGN.md `shadow.dark`（sm: none / md: inset hairline / lg: 1px ring + soft drop），light 微調對齊 DESIGN.md `shadow.light`。覆蓋 "Dark theme SHALL favour inset hairlines over drop shadows, light theme SHALL retain soft drop shadows" 兩個 scenario。驗證：dev tools 看 `<Card>` 的 `box-shadow` computed value，dark=`none`、light=`0 1px 2px rgba(...)`。

## 3. Sonner Toaster 4 變體：透過 CSS data-attr selector 對齊 token（D7）

- [x] 3.1 執行「Sonner Toaster 4 變體：透過 CSS data-attr selector 對齊 token」決策：在 `packages/web/src/index.css` 加四條 `[data-sonner-toast][data-type="..."]` selector，把 success / error / warning / info 各對應到對應 `--color-*` + `--color-*-soft` 透過 override `--normal-bg` / `--normal-border` / `--normal-text`。覆蓋 "Sonner Toaster SHALL render four semantic colour variants via CSS data-attribute selectors" 的四個 scenario。驗證：在 dev page 加四個按鈕分別觸發 `toast.success/.error/.warning/.info`，視覺各自綠/紅/橘/藍；DOM `[data-sonner-toast][data-type="success"]` 的 computed `background-color` 等於 `--color-success-soft` 值。

- [x] 3.2 在 `packages/web/src/components/ui/sonner.tsx` 保留現有 `<Toaster>` JSX 結構不動（「Sonner Toaster 4 變體：透過 CSS data-attr selector 對齊 token」scope boundary 規定不動元件），補一個註解：CSS-only override scope，元件邏輯升級延到 P2。驗證：`git diff packages/web/src/components/ui/sonner.tsx` 只見註解新增、無 import / props / JSX 改動。

## 4. Transcript / Advisor / 其他 me-them consumer 視覺驗證（D11）

- [x] 4.1 執行「Transcript / Advisor / 其他 me-them consumer 視覺驗證」決策第一步：讀 `packages/web/src/components/transcript-pane.tsx`，確認 line 131 / 293-304 所有 `var(--color-them)` / `var(--color-them-soft)` 引用是純 token、無 hardcoded `--primary-hue` 衍生算式。覆蓋 "TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline" 的「counterparty chunk carries all four visual cues in magenta」scenario。驗證：bun test 跑 `transcript-pane.test.tsx` 全綠 + 手動視覺檢查 `/meetings/<id>` 對方 chunk 的 left border / dot / 名字色 = magenta `oklch(0.55 0.15 320)`。

- [x] 4.2 「Transcript / Advisor / 其他 me-them consumer 視覺驗證」第二步：讀 `packages/web/src/components/transcript-chunk-row.tsx` 跟 `packages/web/src/components/speaker-color-popover.tsx`，確認所有 me/them 視覺仍用 `var(--color-me*)` / `var(--color-them*)` 引用、無 hardcoded primary-hue 衍生。覆蓋 "TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline" 的「me chunk uses Glacier Blue」scenario。驗證：bun test 跑 `transcript-chunk-row.test.tsx` 跟 `speaker-color-popover.test.tsx` 全綠 + 手動視覺驗證。

- [x] 4.3 「Transcript / Advisor / 其他 me-them consumer 視覺驗證」第三步：讀 `packages/web/src/components/advisor-pane.tsx`，若有 bubble tint 跟 speaker 綁定，確認用 token 引用；若無，標記為 not-applicable。驗證：grep 該檔無 `oklch(...)` / `#xxxxxx` 直接寫死 + bun test 跑 `advisor-pane.test.tsx` 全綠。

- [x] 4.4 補強 `packages/web/src/lib/transcript-color-schemes.test.ts`：新增測試案例斷言 `_resolveClusterColor("me", pref)` 跟 `_resolveClusterColor("counterparty", pref)` 回傳的 accent 字串確實引用 `var(--color-me)` / `var(--color-them)`（token-driven，不該回 hardcoded oklch）。覆蓋 "TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline" 整個 requirement。驗證：`bun --filter @meeting-playbook/web test transcript-color-schemes` 全綠 + 新加的兩個 case 斷言成立。

## 5. 雜項 hex 清掃

- [x] 5.1 執行「`recording-badge` hex fallback 移除」決策：改 `packages/web/src/components/recording-badge.tsx` 把 `bg-(--color-success, #22c55e)` 的 hex fallback 移除，改成 `bg-(--color-success)`。覆蓋 "Design tokens SHALL be expressed as oklch-based CSS variables across two themes" 的「No raw hex colour appears in component class strings」scenario。驗證：tokens 測試的 hex scan 不再把 `recording-badge.tsx` 列為 violation（可從 allowlist 移除）。

- [x] 5.2 確認「`border-beam.tsx` mask `#000` 視為合規例外」決策落地：`packages/web/src/components/magicui/border-beam.tsx` 的 mask `#000` 仍保留並在 tokens.test.ts 的 allowlist 顯式列出 + justification。驗證：tokens 測試通過 + grep allowlist 確認 `border-beam.tsx` entry 存在且註解寫明「CSS mask alpha context」。

- [x] 5.3 跑 repo-wide grep `grep -rEn '#[0-9a-fA-F]{6}|rgb\\(|rgba\\(' packages/web/src --include='*.{ts,tsx}'`，把不在 allowlist 的命中逐一處理（換 token 或加 justification）。覆蓋 "oklch validation smoke test SHALL guard token format and dark/light parity" 的「New component file introduces raw hex without justification → test fails」scenario，確保不存在未授權 hex。驗證：tokens 測試的「No raw hex colour appears in component class strings」scenario 完全綠。

## 6. 全工作區回歸 + spectra 收尾

- [x] 6.1 跑 `bun --filter @meeting-playbook/web test` 全工作區回歸：tokens.test.ts、transcript-color-schemes.test.ts、transcript-pane.test.tsx、advisor-pane.test.tsx、ui/primitives-smoke.test.tsx 全綠。驗證：bun test exit 0 + 無 skipped 測試。

- [x] 6.2 跑 `bun --filter @meeting-playbook/web build` 確認 Tailwind v4 編譯成功、CSS bundle 內 oklch 值正確輸出。驗證：build exit 0 + grep `dist/assets/*.css` 內出現 `oklch(0.65 0.22 290)` 等預期值。

- [x] 6.3 跑 `bun run lint` / `bun run format`（oxlint + ruff）。驗證：lint exit 0 / no warnings。

- [x] 6.4 dark + light 兩個 theme 各跑一次 `/login`、`/meetings/list`、`/meetings/<existing-id>`（含 transcript + advisor + playbook pane）、`/settings/profile` 視覺迴歸，對齊 DESIGN.md §2 色票跟對比度表。驗證：手動 check sheet — 每頁兩個 theme 各 sign-off "色票對齊 DESIGN.md"。

- [x] 6.5 跑 `spectra validate ui-overhaul-aura-tokens` 跟 `spectra analyze ui-overhaul-aura-tokens --json` 確認 Critical / Warning 為 0；若有，回到對應 task 修正後重跑（最多兩輪）。驗證：兩個指令都 exit 0、analyze JSON `issues` 為空陣列。
