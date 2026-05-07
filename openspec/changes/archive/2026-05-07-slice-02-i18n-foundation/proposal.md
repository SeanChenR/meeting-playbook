- GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/4
- Agent Brief: https://github.com/SeanChenR/meeting-playbook/issues/4#issuecomment-4386425766

## Why

Slice 1 已經把 auth shell 出貨了，但 UI 字串全部寫死在 React 元件裡，等於把 ADR-0022「zh-TW 預設 + en」這條共識凍結在文件層，沒有兌現到程式碼。趁 Slice 2 把 i18n 地基鋪好，後續所有切片才有共同的字串管道；不然每多一個切片，重構成本就再多一層。

## What Changes

- 在 `packages/web` 安裝 `react-i18next`、`i18next`、`i18next-browser-languagedetector`
- 建立 `packages/web/src/locales/zh-TW.json` 與 `en.json`，鏡像 key 樹（`auth`、`common`、`errors` 三大群組）
- 把 login、TOTP enrollment、`Hello, <name>` 既有 UI 字串全部改用 `useTranslation` + `t()`
- 新增 header 區的 locale toggle 元件，切換立即生效、寫入 `localStorage`，預設 `zh-TW`
- Backend 例外回應改採 `{error_code, message}` 形狀；前端依 `error_code` 對應到 locale 字串
- 在 `CLAUDE.md` 加上「新 UI 字串必須同時落入兩份 locale 檔」的 convention 段落

## Non-Goals

- 第三語系（日文等）只在 v1 之後考慮
- RTL 排版支援
- 超出 react-i18next 內建之外的日期 / 數字格式化
- 翻譯使用者產生內容（playbook 內文等）
- SSR 渲染本地化字串
- meeting / playbook / transcript UI 的字串擷取（其他切片各自處理）

## Capabilities

### New Capabilities

(none) — i18n 屬於前端 convention，不是跨切片的系統 contract；遵循 openspec/config.yaml 規則「DO NOT create one spec per slice」。「兩份 locale 檔同步」這條紀律由 CLAUDE.md 承載。

### Modified Capabilities

(none)

## Impact

- `packages/web/package.json` — 新依賴
- `packages/web/src/locales/{zh-TW,en}.json` — 新增
- `packages/web/src/lib/i18n.ts` — 新初始化模組
- `packages/web/src/components/locale-toggle.tsx` — 新元件
- `packages/web/src/components/auth-shell.tsx`、`packages/web/src/routes/login.tsx`、`packages/web/src/routes/signup.tsx`、`packages/web/src/routes/totp/enroll.tsx`、`packages/web/src/routes/totp/verify.tsx`、`packages/web/src/routes/home.tsx` — 字串替換為 `t()`
- `packages/web/src/main.tsx` — i18n bootstrap
- `packages/auth/src/server.ts`、`packages/backend/meeting_playbook/server.py` — 例外輸出統一為 `{error_code, message}`
- `CLAUDE.md` — 新增「兩份 locale 檔同步」約定段落
