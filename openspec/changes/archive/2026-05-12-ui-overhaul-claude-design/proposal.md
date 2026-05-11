## Why

PRD 內 13 個 slice 全部 ship 完，UI 還停留在 dev-minimum 樣式：emoji 拼裝、無 dark mode、token 系統不完整、逐字稿配色對比薄弱、route 之間 NavBar / BackLink / Card 規格不一致。Sean memory `feedback_ui_standards_no_emoji_magicui` 早就拍板「功能完成後一次 UI overhaul」。Claude Design 跑完 11 route 的視覺設計（淺色紫 / 深色橘、oklch token、Inter + Noto Sans TC）放在 `/tmp/claude_design_bundle/`，把這份輸出落地成 production code 就是本 change 的全部範圍。

## What Changes

- 新 token 系統（淺色紫 / 深色橘、oklch、可調 hue/density/radius/contrast，全走 CSS variable），取代現行 zinc + emerald accent
- 新增 dark mode + 全站 theme toggle（NavBar 右側、`prefers-color-scheme` + localStorage）
- 引入 framer-motion / magicui / animate-ui 套件 + 動畫規範（Pane 進場、Tabs 切換、shimmer、pulse、page transition）
- shadcn primitives 增量補齊：Select / DropdownMenu / Tooltip / Skeleton / Sonner toast
- 11 route + 17 component 全部 reskin（從 inline-style design 來、shadcn primitives 落地）
- NavBar / BackLink 位置 + 樣式跨 route 統一
- TranscriptPane 對方 / 我方對比強化：深色 vs 淺色主色 + 5%-20% tint 底色 + 名字色點 + 左 3px border
- MeetingDetail 兩欄 MetadataCard：左 (title/對方/我方/錄音) + 右 (ASR Select + CaptureIndicator sparkline)
- AdvisorPane 改 chat bubble 風格 + suggestion chips
- 既有 8 個 baseline frontend test failures 因 DOM 重組會連帶處理（不再被放著）

## Non-Goals

- 不動既有 backend API 任何契約（純前端視覺重構）
- 不動 i18n keys（既有 zh-TW / en 都保留，只在新元件出現新 key 時補）
- 不動 router / route tree 結構 (`route-tree.tsx` 不變)
- 不重新評估 Playbook 6 個結構化欄位（這個 memory 列在「之後」的另一條獨立工作）
- 不做 `/meetings` kanban 視圖（Sean 已撤回）
- 不做 markdown 渲染 for playbook free-form（同樣留另一條 change）
- 不做 mobile responsive 全面適配（design bundle 是 desktop-first，行動裝置另外開）

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ui-design-system`：token 系統重寫成 oklch + dual-theme (light 紫 / dark 橘)、新增 dark mode 切換契約、新增 5 個 shadcn primitive 規格 (Select / DropdownMenu / Tooltip / Skeleton / Sonner)、新增動畫規範 (framer-motion / magicui / animate-ui 使用邊界)、TranscriptPane speaker 對比強度新契約
- `meeting-detail-layout`：MetadataCard 改兩欄佈局 + 嵌入 CaptureIndicator sparkline + Tab 切換器與 Workspace 並列 + Action bar 拆組
- `meeting-session`：TranscriptChunk 視覺契約強化（speaker 主色深 / 淺 + 5-20% tint 底色 + 左 3px + 名字色點 + tweakable contrast level）

## Impact

- Affected specs: ui-design-system, meeting-detail-layout, meeting-session
- Affected code:
  - New:
    - packages/web/src/lib/theme-provider.tsx
    - packages/web/src/components/theme-toggle.tsx
    - packages/web/src/components/ui/select.tsx
    - packages/web/src/components/ui/dropdown-menu.tsx
    - packages/web/src/components/ui/tooltip.tsx
    - packages/web/src/components/ui/skeleton.tsx
    - packages/web/src/components/ui/sonner.tsx
    - packages/web/src/lib/motion-presets.ts
  - Modified:
    - packages/web/src/index.css (token 全部翻新)
    - packages/web/src/components/protected-shell.tsx (含 ThemeProvider + ThemeToggle)
    - packages/web/src/components/auth-shell.tsx
    - packages/web/src/components/advisor-pane.tsx
    - packages/web/src/components/transcript-pane.tsx
    - packages/web/src/components/playbook-pane.tsx
    - packages/web/src/components/summary-pane.tsx
    - packages/web/src/components/capture-indicator.tsx
    - packages/web/src/components/asr-provider-selector.tsx
    - packages/web/src/components/recording-badge.tsx
    - packages/web/src/components/rerun-button.tsx
    - packages/web/src/components/layout-switcher.tsx
    - packages/web/src/components/locale-toggle.tsx
    - packages/web/src/components/headphones-hint.tsx
    - packages/web/src/components/chat-input.tsx
    - packages/web/src/components/chat-message-list.tsx
    - packages/web/src/components/ui/alert.tsx
    - packages/web/src/components/ui/badge.tsx
    - packages/web/src/components/ui/button.tsx
    - packages/web/src/components/ui/card.tsx
    - packages/web/src/components/ui/input.tsx
    - packages/web/src/components/ui/label.tsx
    - packages/web/src/components/ui/separator.tsx
    - packages/web/src/components/ui/tabs.tsx
    - packages/web/src/components/ui/alert-dialog.tsx
    - packages/web/src/components/ui/avatar.tsx
    - packages/web/src/routes/home.tsx
    - packages/web/src/routes/login.tsx
    - packages/web/src/routes/signup.tsx
    - packages/web/src/routes/totp/enroll.tsx
    - packages/web/src/routes/totp/verify.tsx
    - packages/web/src/routes/meetings/list.tsx
    - packages/web/src/routes/meetings/new.tsx
    - packages/web/src/routes/meetings/detail.tsx
    - packages/web/src/routes/meetings/calendar.tsx
    - packages/web/src/routes/calendar/upcoming.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - packages/web/package.json (新依賴：framer-motion / magicui / animate-ui / 多個 radix primitives)
  - Removed: (none)
