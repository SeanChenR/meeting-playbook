## 1. 依賴與初始化

- [x] 1.1 [P] [AC-1] 寫失敗測試 `packages/web/src/lib/i18n.test.ts` 預期可以從 `./i18n` import `i18n` instance；`bun install` 加入 `react-i18next`、`i18next`、`i18next-browser-languagedetector`，建立 `packages/web/src/lib/i18n.ts` 走 react-i18next 與 i18next-browser-languagedetector 為依賴 章節的設定，使測試 GREEN
- [x] 1.2 [P] [AC-1] [AC-4] 在 `packages/web/src/main.tsx` import `./lib/i18n`，寫測試確認 default locale 為 `zh-TW`（無 localStorage 預設）；落實 語系偵測鏈與 fallback 行為 設定，使測試 GREEN

## 2. Locale 檔骨架

- [x] 2.1 [AC-2] 為 Locale 檔結構（鏡像 key 樹，feature-area 分群）建立 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json`，先放入 `common`、`auth`、`errors` 三個空物件群組；寫測試 `packages/web/src/locales/locales.test.ts` 對比兩份 JSON 的 key 樹 deep equal（先 RED 因為缺鏡像條件，再 GREEN）
- [x] 2.2 [P] [AC-2] [AC-9] 為 missing-key 行為寫單元測試（呼叫只存在於 zh-TW 的 key 在 en 模式下取得 fallback 並觸發 console.warn），於 `lib/i18n.ts` 加上 missingKeyHandler 使測試 GREEN

## 3. 既有畫面字串擷取

- [x] 3.1 [AC-3] 為 `packages/web/src/routes/login.tsx` 加上 render-with-translation 測試（zh-TW 顯示中文標題、en 顯示英文標題）；補上 `auth.login.*` keys、改用 `useTranslation()`，使測試 GREEN
- [x] 3.2 [P] [AC-3] 為 `packages/web/src/routes/signup.tsx` 重複 3.1 流程，補上 `auth.signup.*` keys
- [x] 3.3 [P] [AC-3] 為 `packages/web/src/routes/totp/enroll.tsx` 重複 3.1 流程，補上 `auth.totp.enroll.*` keys
- [x] 3.4 [P] [AC-3] 為 `packages/web/src/routes/totp/verify.tsx` 重複 3.1 流程，補上 `auth.totp.verify.*` keys
- [x] 3.5 [P] [AC-3] 為 `packages/web/src/routes/home.tsx` 的 "Hello, <name>" 加上 render-with-translation 測試（zh-TW 與 en 各一次）；補上 `auth.home.greeting` 並使用 i18next interpolation 渲染 name
- [x] 3.6 [AC-3] 為 `packages/web/src/components/auth-shell.tsx` 加上字串擷取測試，補上 `auth.shell.*` keys

## 4. Locale toggle UI

- [x] 4.1 [AC-5] 為 Locale toggle 元件 + localStorage 持久化 寫元件測試 `packages/web/src/components/locale-toggle.test.tsx`：點擊切換後 `i18n.language` 立即變更、畫面字串隨之改變、不觸發 page reload；建立 `packages/web/src/components/locale-toggle.tsx` 使測試 GREEN
- [x] 4.2 [AC-5] [AC-6] 在 `auth-shell.tsx` 的 header 區掛上 `<LocaleToggle />`；寫整合測試模擬切換 → reload（清除 React 樹再 mount）→ 驗證 localStorage 中 `meeting-playbook.locale` 為使用者選擇的值且初始 render 為該語系

## 5. Backend error_code 契約

- [x] 5.1 [AC-7] 為 Backend error_code 契約與前端對應 寫 pytest `packages/backend/tests/test_error_envelope.py`：呼叫 `/api/me` 不帶 `X-User-Id` 時回傳 JSON `{error_code, message}` 形狀；於 `packages/backend/meeting_playbook/server.py` 新增 exception handler 使 GREEN，同步更新 Slice 1 受影響測試 (`tests/test_api_me.py`、`tests/test_integration_round_trip.py`)
- [x] 5.2 [AC-7] 為 Bun gateway 寫 `packages/auth/src/__tests__/error-envelope.test.ts`：未授權 401 與 5xx fallthrough 都回傳相同 `{error_code, message}` 形狀；於 `packages/auth/src/server.ts` 統一錯誤輸出使 GREEN
- [x] 5.3 [P] [AC-7] 為前端 `localizedErrorMessage(errorCode, t)` 寫單元測試 `packages/web/src/lib/i18n-errors.test.ts`：已知 code 回傳對應字串、未知 code 回退到 `errors.common.unknown`；建立 `packages/web/src/lib/i18n-errors.ts` 使 GREEN
- [x] 5.4 [AC-7] 在 login 流程實際串上 `localizedErrorMessage`：寫 `login.test.tsx` 補一個情境，模擬後端回 `{error_code: "auth.invalid_credentials", message: "..."}` 時畫面顯示對應 zh-TW 與 en 字串；補上 `errors.auth.*` keys 使 GREEN

## 6. Convention 文件

- [x] 6.1 [AC-10] 在 CLAUDE.md convention 段落 對應位置（`CLAUDE.md` Domain glossary 之後）新增 `## i18n convention` 章節，敘述「新 UI 字串必須同時加進 zh-TW.json 與 en.json」並附最小範例（`auth.signin.button` 在兩份 JSON 出現）

## 7. 收尾

- [x] 7.1 [AC-8] [AC-9] 為「sample component 在兩種 locale 下渲染」寫一個獨立測試 `packages/web/src/lib/i18n-render.test.tsx`，作為 acceptance criterion 的 self-evidence；missing-key 行為亦在此測試裡再驗一次
- [x] 7.2 跑全套測試 `bun test` 與 `cd packages/backend && uv run pytest`，確認 Slice 1 所有測試在新 error envelope 下仍綠
- [x] 7.3 Verify all 10 acceptance criteria from agent brief are checked off in GitHub Issue #4
