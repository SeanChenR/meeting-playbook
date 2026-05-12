## 1. Foundation — wrapper + helpers

- [x] 1.1 [Decision 1: Add `motion` package vs alias from `framer-motion`] [Icon library usage SHALL follow the lucide-react / animate-ui split] Add Vite resolve aliases to `packages/web/vite.config.ts`: `{ find: "motion/react", replacement: "framer-motion" }` and `{ find: "motion", replacement: "framer-motion" }`. **驗證**：`bun run build` 成功；inspect dist output 確認沒有重複的 `motion` chunk；`bun test src/components/workspace.test.tsx` 仍綠（framer-motion `motion` 物件還能被原 import 抓到）。

- [x] 1.2 [P] [Behavior contract] 新增 `packages/web/src/hooks/use-is-in-view.ts`，從 animate-ui registry `https://animate-ui.com/r/icons-icon.json` 的 `files` payload 抓 `useIsInView` 實作 port 過來；接受 `(ref, options?: UseInViewOptions)` 並回傳 `boolean`。**驗證**：新增 `packages/web/src/hooks/use-is-in-view.test.tsx`：在 happy-dom 下 mount component + observe，模擬 IntersectionObserver entry 後 hook return value 變 true。

- [x] 1.3 [P] [Behavior contract] 新增 `packages/web/src/components/animate-ui/icons/slot.tsx` — 從 registry 的 wrapper 拉 `Slot` primitive（forwardRef + `asChild` props 合併），支援 `WithAsChild` 類型 export。**驗證**：`bunx tsc --noEmit` 0 error；新增 `tests/components/animate-ui/slot.test.tsx`：(a) 預設渲染 wrapper element、(b) `asChild` 時把 props 注入 first child。

- [x] 1.4 [Behavior contract] [Decision 4: Centralise install location] [Decision 5: Spec policy lives in ui-design-system] 新增 `packages/web/src/components/animate-ui/icons/icon.tsx` — 從 `https://animate-ui.com/r/icons-icon.json` curl 完整 `files[0].content` 寫進來；唯一 import `motion/react` 的檔；export `AnimateIcon` + `getVariants` + 型別 `DefaultIconProps`。**驗證**：`bunx tsc --noEmit` 0 error；新增 `tests/components/animate-ui/icon.test.tsx`：mount 一個假 icon component using wrapper，斷言 `<svg>` 根節點存在 + 預設 reduced-motion=reduce 時沒有 motion 相關 inline style。

## 2. Install 15 icons via registry

- [x] 2.1 [Decision 2: Curated 15-icon subset, not full sweep] 一次性安裝 15 顆 animate-ui icons 到 `packages/web/src/components/animate-ui/icons/`。對每顆 icon 跑 `curl -sL https://animate-ui.com/r/icons-<name>.json` 抓 JSON、parse `files[0].content`、寫入對應的 `<name>.tsx` 檔。15 個 name：`arrow-left`, `copy`, `download`, `languages`, `loader`, `lock`, `log-out`, `mic`, `plus`, `refresh-cw`, `shield`, `shield-check`, `sparkles`, `square`, `trash`。**驗證**：15 個檔案存在；`bunx tsc --noEmit` 0 error；smoke test `tests/components/animate-ui/icons-smoke.test.tsx` mount 每顆 icon 並斷言 `<svg>` 渲染。

## 3. Sweep call sites — Group A & B

- [x] 3.1 [P] [Decision 3: Hover-only trigger by default] 改 `packages/web/src/components/metadata-card.tsx`：把 `import { Mic, RefreshCw, Square, Trash2 } from "lucide-react"` 換成 from `../animate-ui/icons/mic` / `refresh-cw` / `square` / `trash`；每個 JSX call site 加 `animateOnHover` prop。**驗證**：既有 `tests/components/metadata-card.*` 或 `routes/meetings/detail.test.tsx` 既有的 metadata-card 結構斷言全綠。

- [x] 3.2 [P] [Decision 3: Hover-only trigger by default] 改 `packages/web/src/components/back-link.tsx`：lucide `ArrowLeft` → animate-ui `arrow-left`；JSX 加 `animateOnHover`。**驗證**：`tests/components/back-link.test.tsx` 3 個 case 全綠（含 `<svg>` 存在 + 預設 fallback 文字）。

- [x] 3.3 [P] [Decision 3: Hover-only trigger by default] 改 `packages/web/src/components/protected-shell.tsx`：lucide `LogOut` → animate-ui `log-out`；trigger 用 `animateOnHover`。**驗證**：`tests/components/protected-shell.test.tsx` 4 個 case 全綠（含 logout-button testid）。

- [x] 3.4 [P] [Decision 3: Hover-only trigger by default] 改 `packages/web/src/components/summary-pane.tsx`：lucide `Copy / Download / RefreshCw / Sparkles` → animate-ui counterparts；每個 button icon 加 `animateOnHover`。**驗證**：`tests/components/summary-pane.test.tsx` 12 個 case 全綠（含 6.5a-d 結構斷言）。

- [x] 3.5 [P] [Decision 3: Hover-only trigger by default] 改 `packages/web/src/components/locale-toggle.tsx`：lucide `Languages` → animate-ui `languages`；trigger 用 `animateOnHover`。**驗證**：`tests/components/locale-toggle.test.tsx` 4 個 case 全綠。

- [x] 3.6 [P] [Decision 3: Hover-only trigger by default] [Failure modes: spinner uses animate="loop"] 改 auth routes（`packages/web/src/routes/login.tsx`、`signup.tsx`、`totp/enroll.tsx`、`totp/verify.tsx`）：lucide `Loader2 / Lock / Shield / ShieldCheck / Copy / Download` → animate-ui counterparts；`Loader` 用 `animate="loop"`，其他 hero / action 用 `animateOnHover`。**驗證**：4 個 route test 檔案全綠（每個檔 isolation 跑）。

- [x] 3.7 [P] [Decision 3: Hover-only trigger by default] 改 meeting / calendar / home routes（`packages/web/src/routes/home.tsx`、`meetings/list.tsx`、`meetings/new.tsx`、`meetings/calendar.tsx`、`calendar/upcoming.tsx`）：lucide `Sparkles / Plus / RefreshCw` → animate-ui counterparts；`animateOnHover` only。注意 `Calendar` icon（用在 meetings/list 卡片底部、home CTA 按鈕）留 lucide — 它在 Group C。**驗證**：5 個 route test 檔案全綠。

## 4. Acceptance

- [x] 4.1 [Acceptance criteria] 全 suite 驗證：`bun test` 321+/0 fail、`bunx tsc --noEmit` 0 error、`bunx oxlint` 0 warning、`bun run build` 成功。**驗證**：四指令 exit code 0；對比 swap 前後 `bun run build` 輸出的 `dist/assets/index-*.js` 大小差異 < 50 KB（icon wrapper + 15 icons 預期 ~30 KB gzipped）。

- [x] 4.2 [Scope boundaries (in / out)] 確認沒越界：`git diff main..HEAD --stat -- packages/backend packages/auth packages/web/src/route-tree.tsx` 顯示 0 修改；剩餘 lucide 進口列表精確等於 Group C 11 顆（grep 驗證）。**驗證**：`grep -rh 'from "lucide-react"' packages/web/src | sed ...` 結果僅含 `Check / ChevronUp / ChevronDown / ChevronLeft / ChevronRight / Columns3 / Rows3 / Sun / Moon / Monitor / Calendar`。
