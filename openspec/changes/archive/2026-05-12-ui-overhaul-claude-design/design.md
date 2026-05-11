## Context

PRD 完工後的 UI overhaul。Claude Design 跑出 11 個 route 的設計（淺色紫 / 深色橘、oklch token、Inter + Noto Sans TC、tweakable hue/density/radius/contrast），存在 `/tmp/claude_design_bundle/meeting-playbook/project/`。Bundle 內元件全部 inline-style + CSS variable 寫的，Sean 拍板 **shadcn/radix headless 重寫**（不 port inline-style），分 6 phase 一個 change ship 完。

**現有 UI 痛點（重構前）：**

- `index.css` token 只有 light mode，zinc base + emerald accent，跟 design bundle 完全不同調
- 沒 dark mode，theme provider / toggle 都不存在
- 11 route 各自手刻 layout，NavBar / BackLink 位置與樣式不一致
- TranscriptPane 對方 / 我方僅用左 4px border 區隔，平均對比不足
- 缺 shadcn primitives：Select（AsrProviderSelector 在用 native select）、Tooltip、Skeleton、Sonner toast、DropdownMenu
- 8 個 baseline frontend test failures（authClient / Login / Signup / NewMeeting / MeetingDetail / UpcomingEvents / Home 兩條）跟 TanStack Router 結構有關，DOM 大改後一定要連同處理

**範圍：** 純前端 (`packages/web`) 視覺重構 + theme system + 動畫系統。Backend 不動。i18n keys 既有保留，新元件出現新 key 才補。

## Goals / Non-Goals

**Goals:**

- Token 系統翻新成 oklch + dual-theme（light 紫 hue 280 / dark 橘 hue 50），全走 CSS variable
- Dark mode 支援：ThemeProvider + 全站 toggle，`prefers-color-scheme` 初始化 + localStorage 持久化
- 11 個 route 視覺對齊 Claude Design bundle
- TranscriptPane 對方 / 我方對比強化（speaker 主色深 vs 淺 + 5-20% tint 底色 + 名字旁色點 + 左 3px border）
- 引入 framer-motion / magicui / animate-ui 套件 + 動畫規範
- NavBar / BackLink 跨 route 統一規格
- 既有 8 個 baseline frontend test failures 全部修掉
- 既有 tests 通過率：250 passed 提升到 290 passed 以上（含新元件 tests，無 regression）
- TypeScript 零 error（含舊 totp / test/fixtures/router.tsx 的型別問題）

**Non-Goals:**

- 不動 backend / API 契約
- 不動 router 結構（`route-tree.tsx` 不變、不增不減 route）
- 不動 i18n key 命名（既有保留 + 新元件補新 key，不重命名既有）
- 不重新評估 Playbook 6 個結構化欄位（另一條 memory deferred）
- 不做 `/meetings` kanban（Sean 撤回）
- 不做 markdown 渲染 for playbook free-form（另一條 deferred change）
- 不做 mobile responsive 全面適配（design bundle 是 desktop-first）
- 不引入 storybook / chromatic
- 不重寫 backend 設定 / migration
- 不改 ESLint / oxlint 規則
- 不引入 CSS-in-JS library（保持 Tailwind v4 + CSS variable）

## Decisions

### Decision 1: shadcn/radix headless 重寫（不 port inline-style）

Sean 拍板。所有 design bundle 的 primitive 用 shadcn cli 對應安裝：

- 已有：`Card / Button / Input / Label / Badge / Avatar / Separator / Tabs / Alert / AlertDialog`
- 補齊：`Select / DropdownMenu / Tooltip / Skeleton / Sonner`
- Domain-specific（非 primitive）：`TranscriptChunk / CaptureIndicator / ChatBubble / Pane wrapper` — 自寫，不走 shadcn

**Rationale**：Inline-style 跨 prop 重用差、無 a11y、無 type 推導；shadcn / radix 對齊業界、含 a11y、headless 允許 Tailwind class 完全自由。

**Alternatives considered**：
- A: Port inline-style 轉 Tailwind — 短期快但中期重複造輪子
- B (採用): shadcn/radix + Tailwind v4
- C: Headless UI / Reach UI — radix 生態最大，不選

### Decision 2: 1 change 6 phase，spec deltas 統一 archive

Phase 切分（每 phase ~5-8 tasks）：

1. **Foundation**: token 翻新（oklch dual-theme）+ ThemeProvider + theme-toggle + 載入字體 + 5 個新 shadcn primitive
2. **Shells**: ProtectedShell + AuthShell（NavBar / BackLink 規格、max-width 1200 + fullBleed）+ locale-toggle 改成 dropdown
3. **Auth routes**: home / login / signup / totp/enroll / totp/verify
4. **Meeting routes (non-detail)**: meetings/list / meetings/new / meetings/calendar / calendar/upcoming
5. **Detail centerpiece**: detail.tsx + MetadataCard 兩欄 + Tabs + Workspace 3-pane + Summary tab
6. **Panes polish + animations**: playbook-pane / transcript-pane（對比強化）/ advisor-pane（chat bubble）/ summary-pane + framer-motion / magicui / animate-ui 接入 + 修 8 個 baseline test failures + i18n parity

**Rationale**：500 px / 個人專案，跨 phase 中段不需要可 ship 的視覺一致；但 phase 內必需綠燈（每 phase 結束 backend test + frontend test 各別跑過、dev stack 啟動正常）。

### Decision 3: Dark mode 用 `data-theme` 屬性 + ThemeProvider Context

```tsx
// theme-provider.tsx
type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; resolved: "light" | "dark"; setTheme: (t: Theme) => void }>(...);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("mp-theme") as Theme ?? "system");
  const resolved = theme === "system" ? (prefers dark ? "dark" : "light") : theme;
  useEffect(() => document.documentElement.setAttribute("data-theme", resolved), [resolved]);
  useEffect(() => localStorage.setItem("mp-theme", theme), [theme]);
  return <ThemeContext.Provider value={{ theme, resolved, setTheme }}>{children}</ThemeContext.Provider>;
}
```

`index.css` 用 `[data-theme="light"]` / `[data-theme="dark"]` 兩 block 切 token，預設 `:root` 走 light。

**Alternatives considered**：
- A: Tailwind v4 `@theme` block + media query 自動切 — 不能手動覆蓋
- B (採用): `data-theme` + Context
- C: `next-themes` library — 但 Vite 沒 SSR、不需要 hydration mismatch 處理

### Decision 4: 動畫套件分工

- **framer-motion**：React 元件動畫（Pane 進場 stagger、Tabs 切換淡入、Modal scale + fade、buttons hover spring）
- **magicui**：複雜視覺效果（shimmer skeleton 已內建、可選 NumberTicker for stats card、Particles for hero、Marquee 可能用於 Calendar 匯入列表）
- **animate-ui**：page transition（route change overlay）+ layout transition（三欄 上下切換的 reorder 動畫）

衝突時優先 framer-motion（最成熟）；magicui / animate-ui 只挑各自獨家強項。

**Rationale**：Sean 明確選了三個都要。framer-motion 是 base layer，另外兩個是 sugar。

### Decision 5: 既有 8 個 baseline test failures 在 phase 6 一起修

當前清單：
- authClient.test 兩條（signIn.social / twoFactor.verifyTotp via plugin）
- Home route: renders Enable two-factor link when twoFactorEnabled is false
- Signup route: renders link back to login
- Login route: renders link to signup page
- UpcomingEvents page: import 觸發 POST 然後 navigate
- MeetingDetail route: delete confirmation flow
- NewMeeting form: submit 然後 navigate

Root cause 多半是 TanStack Router test harness（`test/fixtures/router.tsx` 那個 `trailingSlash` 型別問題）+ component DOM 改動。Phase 6 DOM 重構完成後一起 audit + 補修。

### Decision 6: 既有 i18n keys 保留 + locale parity

`locales.test.ts` 的 deep-equal 守衛繼續用。新元件出現新 key（譬如 `theme.toggle.light` / `theme.toggle.dark`、`navbar.userMenu`）要同步加 `zh-TW` + `en`。不重命名既有 keys（避免動到所有 callsite）。

### Decision 7: Demo 資料只當設計參考、production 走空 state / API

Bundle 內「林經理 / Q2 roadmap / cohort 留存 18%」是 mockup。Production 元件 props 接 API 結果 + empty state 設計依 design bundle。Stat cards / Suggestion chips 等如果 data source 還沒接，先 hardcode 暫定值但 wrap 在 TODO 註解 — phase 6 audit 時若還沒 source 就改 empty state。

### Decision 8: Mobile / 響應式 design 暫時不處理

Design bundle 為 desktop-first，min-width 1200 才正常呈現。Phase 內所有頁面 desktop 必要對齊 Bundle；行動裝置從「不要崩」開始（基本 viewport meta + 不超寬），不做 mobile-specific 重排。後續再開單獨 change。

## Implementation Contract

### Behavior contract

1. **Theme system**：使用者打開 app 第一次 讀 `prefers-color-scheme` 決定主題；右上 toggle 切換 寫 localStorage + 即時切 `data-theme` 屬性；reload 後讀 localStorage 沿用。
2. **NavBar 跨 route 一致**：所有 `ProtectedShell` 內的 route 上方都有同一個 56px sticky NavBar；左側 logo + 右側 locale toggle / theme toggle / avatar / logout button 都在固定位置。`AuthShell` (login/signup/totp) 不顯示 NavBar，只在右上角浮 theme toggle。
3. **BackLink 跨 route 一致**：所有非 list / 非 home 的 route，main 區第一行 = `BackLink`（ghost button + left arrow + 「返回列表」/「返回」文字），點擊回上層 route。
4. **TranscriptPane 對方 / 我方**：每個 chunk 必定有「3px 左邊 border」+「主色（深 / 淺變體）」+「5-20% tint 背景」+「名字旁色點」。對方深色變體、我方淺色變體；雙眼掃過明顯分群。`data-speaker` attribute 維持，現有 e2e selectors 不破。
5. **MetadataCard**：左欄含 status badge + title + 對方/我方/錄音 grid；右欄含 ASR Select（含切換 hint）+ CaptureIndicator（兩條 stream sparkline + pulse dot）。下方 Separator + action bar（開始/結束/重新轉錄/匯出/刪除）。
6. **動畫**：Pane 進場 stagger 80ms 間隔 + 4px translateY 0；Tabs 切換內容 150ms cross-fade；Card hover shadow + 1px translateY；Button hover 微 scale；route change 100ms opacity transition。可被 `prefers-reduced-motion` disable。
7. **i18n**：既有 zh-TW / en key 全留；新元件 string 必須同時加兩 locale 才能合進主分支（`locales.test.ts` deep-equal guard）。
8. **既有 tests**：250 passed 提升到 290 passed 以上；8 baseline failures 全部變綠；新 component tests 補進（每個 phase 至少 2 個新 test）。

### Data shapes (TypeScript)

```typescript
// theme-provider.tsx
type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;          // raw user preference
  resolved: ResolvedTheme; // after resolving "system"
  setTheme: (theme: Theme) => void;
}

// motion-presets.ts
import type { Variants, Transition } from "framer-motion";

export const paneEnter: Variants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.18, ease: "easeOut" } },
};
export const paneStagger: Transition = { staggerChildren: 0.08 };
export const tabContent: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.15 } },
  exit: { opacity: 0, transition: { duration: 0.10 } },
};

// CSS variable contract — index.css
// Token namespace 對應 design-tokens.css 那份原樣 import 進 :root + [data-theme="dark"]
// 全部以 var(--color-primary) / var(--space-N) / var(--radius-N) 形式被消費
```

### Failure modes

- **Theme localStorage 損毀**：fallback 回 `system`，不 throw
- **prefers-color-scheme 不支援** (舊瀏覽器)：fallback 回 `light`
- **framer-motion / magicui / animate-ui 安裝失敗**：phase 1 task 必須 ship clean install + lockfile，避免 phase 6 才爆炸
- **既有 i18n key 在重寫元件後找不到 component caller**：build time fails dev server 早期會抓到，不到 production
- **Test harness 對新元件不認**：TanStack Router test fixture 是已知壞區（type error），phase 6 audit 必須處理

### Acceptance criteria

- **每個 phase 結束**：`bun test` + `bun run build` + dev server 啟動三項皆通過；視覺對齊 design bundle 對應 route
- **整 change 結束**：
  - `bun test`：250 提升到 290 passed 以上（8 baseline 修掉、新元件 tests 補入）
  - `bunx tsc --noEmit`：0 error
  - `bunx oxlint`：0 error
  - 11 個 route 都 dark / light 切換正常
  - Sean 手動 walkthrough 11 route 確認視覺對齊 design bundle

### Scope boundaries (in / out)

**In scope:**

- `packages/web/src/` 內所有 components / routes / lib / locales（部分 keys）/ index.css
- `packages/web/package.json`（新 deps）
- 既有 frontend tests 全套
- 8 個 baseline test failures 修

**Out of scope:**

- Backend code (`packages/backend/**` / `packages/auth/**`)
- DB schema / migrations
- Spectra spec 主檔（只動 deltas）
- ADR 新增（如果動到方向性決策可以加 ADR，但本 change 預期動不到 ADR）
- 任何新 route / route tree 異動
- Mobile responsive
- i18n key renaming
