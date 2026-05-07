## Context

Slice 1 已完成（archived），auth shell 在 `packages/web/src/routes/{login,signup,home,totp/{enroll,verify}}.tsx` 與 `packages/web/src/components/auth-shell.tsx` 中以英文（部分繁中）硬編碼字串呈現。`packages/auth/src/server.ts` 對非 `/api/auth/*` 的請求做 reverse proxy；`packages/backend/meeting_playbook/server.py` 則對外回傳純文字或英文錯誤。當前不存在 i18n 機制、locale 切換、共用 error 對應表。

ADR-0008 已宣告 i18n 採 react-i18next；ADR-0022 進一步固定 zh-TW（預設）+ en，且要求「backend 例外用 stable error code，前端自負本地化」。本 slice 的目的是把這兩條 ADR 兌現到程式碼。

## Goals / Non-Goals

**Goals:**

- 前端引入 react-i18next + 語系偵測鏈（URL → cookie → localStorage → navigator）
- 兩份 locale JSON（鏡像 key 樹）+ TypeScript 型別（從 zh-TW.json 自動推導）
- 既有 auth 相關畫面字串改走 `t()`
- Header locale toggle 元件，切換立即生效並 persist 到 localStorage
- Backend 例外契約 `{error_code, message}`，前端 `error_code` → 本地化字串對應
- CLAUDE.md 新增「兩份 locale 檔同步」 convention

**Non-Goals:**

- 第三語系
- RTL
- 翻譯 user-generated content
- meeting / playbook / transcript UI 字串擷取（其他 slice 處理）
- SSR locale rendering

## Decisions

### react-i18next 與 i18next-browser-languagedetector 為依賴

加入 `i18next`、`react-i18next`、`i18next-browser-languagedetector` 三個套件至 `packages/web/package.json`。版本鎖定當下最新 stable major（i18next ^23, react-i18next ^14, detector ^8）。

替代方案考慮：FormatJS、LinguiJS — 兩者 React 整合度與生態都不如 react-i18next；且 ADR-0008 已指定 react-i18next。

### 語系偵測鏈與 fallback 行為

`detection.order = ['querystring', 'cookie', 'localStorage', 'navigator']`，`lookupLocalStorage = 'meeting-playbook.locale'`，`caches = ['localStorage']`。`fallbackLng = 'zh-TW'`、`supportedLngs = ['zh-TW', 'en']`、`load = 'currentOnly'`（避免 i18next 把 `zh-TW` 退化成 `zh`）。

替代方案：只用 localStorage — 不夠彈性，未來想做 deep link 帶 `?lang=en` 會卡。

### Locale 檔結構（鏡像 key 樹，feature-area 分群）

兩份 JSON 位於 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json`，top-level 三大群組：`common`（通用按鈕、navigation）、`auth`（login / signup / TOTP 訊息）、`errors`（error_code → message 對應）。

`saveMissing = true` + 自訂 `missingKeyHandler`：dev 環境 `console.warn`，prod 安靜退化為 key 字串本身。

替代方案：扁平 key（如 `auth.login.title`） — 已採用扁平命名的 nested JSON 結構（巢狀物件，`t('auth.login.title')` 訪問），可讀性與工具支援皆佳。

### Locale toggle 元件 + localStorage 持久化

新增 `packages/web/src/components/locale-toggle.tsx`，渲染為 shadcn `<Select>` / `<DropdownMenu>` 兩擇一；切換 `i18n.changeLanguage(next)`，detector 的 cache 自動寫回 `meeting-playbook.locale` key 至 `localStorage`。

`packages/web/src/components/auth-shell.tsx` 在 header 區掛上 `<LocaleToggle />`，未登入頁亦可見。

### Backend error_code 契約與前端對應

#### 後端輸出契約

FastAPI exception handler（位於 `packages/backend/meeting_playbook/server.py`）回傳：

```json
{ "error_code": "auth.gateway_bypass", "message": "Request did not arrive through the gateway" }
```

`error_code` 為 snake_case 前綴 + 點分組（例：`auth.invalid_totp`、`auth.gateway_bypass`、`common.internal_error`）。Bun gateway（`packages/auth/src/server.ts`）原本可能丟出 plain 401，本 slice 收斂為相同形狀。

#### 前端對應

`packages/web/src/lib/i18n-errors.ts` 匯出 `localizedErrorMessage(errorCode: string, t: TFunction): string`，內部以 `t(` errors.${errorCode}` , { defaultValue: t('errors.common.unknown') })` 轉換。Locale JSON 的 `errors` 群組鏡像 backend 的 error_code 命名。

替代方案：回傳直接本地化好的字串 — 違反 ADR-0022「backend locale-agnostic」原則。

### CLAUDE.md convention 段落

在 `CLAUDE.md` 既有 "Domain glossary" 之後加入新段落 `## i18n convention`，敘述「新 UI 字串必須同時加進 zh-TW.json 與 en.json，否則 PR 退回」並附最小範例（例：`auth.signin.button` 在兩份 JSON 出現）。

## Risks / Trade-offs

- [風險] react-i18next 與 Bun runtime 的 SSR 相容性 → 緩解：本專案是純 SPA（Vite client-only），無 SSR 風險
- [風險] localStorage 在私密瀏覽情境失效 → 緩解：fallback 至 navigator detector + memory，不影響可用性
- [風險] Backend 例外契約變更可能讓 Slice 1 的 `tests/test_api_me.py`、`tests/test_integration_round_trip.py` 改寫 → 緩解：本 slice 任務內含「更新被影響測試」步驟
- [風險] 兩份 locale JSON 漂移（其中一邊缺 key）→ 緩解：(a) dev 環境 missingKeyHandler 顯式警告；(b) 加單元測試對比兩份 JSON 的 key 樹 deep equal

## Migration Plan

1. 安裝依賴 → 失敗的 import 測試 RED；`bun install` GREEN
2. 建立 `lib/i18n.ts`、locale JSON、`main.tsx` 注入 → render smoke test GREEN
3. 抽取既有畫面字串 → 每個畫面逐一 RED-GREEN
4. 新增 `LocaleToggle` 元件 + 注入 auth-shell header
5. Backend exception handler 改 `{error_code, message}`，更新 Slice 1 受影響測試
6. 前端 `i18n-errors.ts` 落地，於 login 流程示範一次 error_code → t() 對應
7. CLAUDE.md 補上 convention 段落
8. 跑全套測試（`bun test` + `pytest`）+ 對 GitHub Issue #4 acceptance criteria 逐條打勾

無 DB 變更、無 rollback 需要；任何回滾即回退 commit。

## Open Questions

- locale toggle 的視覺呈現（drop-down vs. 兩顆按鈕）→ 預設先用 shadcn `<Select>`；apply 階段若覺得醜再調
- Backend error_code 命名空間是否需要在 spec 化的 `auth-gateway-contract` 增 requirement → 預設不在本 slice 動 spec（仍是 frontend convention 為主）；未來若有 Slice 涉及更多錯誤碼，再升級為跨切片 contract
- `bun test` 對 `.json` import 與 i18next instance 的隔離行為（是否每個測試需 reset）→ apply 階段以 `beforeEach` cleanup 處理；若有 flake 再回頭調 vitest-style isolate
