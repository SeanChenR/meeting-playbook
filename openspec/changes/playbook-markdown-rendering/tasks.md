<!--
本 change 是純前端 refactor（一個 useState 初始值翻轉 + 一個 effect fallback 翻轉
+ 對應 spec / 測試更新），所以 task 數量刻意精簡。每個 task 仍依 TDD 寫
red → green → refactor，並且明確指出觀察行為 + 驗證指令。
-->

## 1. 紅燈：寫失敗測試對齊新的 default sub-mode 契約（D5 — 測試策略：翻轉既有 mount-time assertion，新增「點 Edit 才看到 textarea」path）

- [x] 1.1 在 `packages/web/src/components/playbook-pane.test.tsx` 新增 / 翻轉測試「PlaybookPane UI exposes a free-form view, a structured view, and a save action」對應 mount-time assertion：mount 後 `data-testid="markdown-preview"` SHALL be in DOM、`<textarea>` SHALL NOT be in DOM、`freeform-preview-tab` 的 `aria-pressed === "true"`、`freeform-edit-tab` 的 `aria-pressed === "false"`。此測試實作 design.md 內 Implementation Contract 之 Behavior（mount 後 rendered preview 為觀察結果）與 Acceptance Criteria 第一條。驗證方式：`bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 必須出現此測試 fail（紅燈）。
- [x] 1.2 [P] 在同檔新增測試「User clicks Edit to switch into the textarea」（D3 — 既有 testid 與 aria attribute 全部保留 的契約）：模擬 `fireEvent.click(getByTestId("freeform-edit-tab"))` 後 textarea 出現、`markdown-preview` 不在 DOM、`aria-pressed` 反轉。對應 design.md Implementation Contract 之 Behavior「Edit toggle」段落。驗證方式：`bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 顯示新測試紅燈。
- [x] 1.3 [P] 在同檔新增測試「User switches back from Edit to Preview without losing draft」：在 Edit mode 修改 textarea draft，切回 Preview 後 `<MarkdownPreview>` 渲染包含修改後內容；再切回 Edit textarea value 仍是修改後 draft。此測試保護 design.md Implementation Contract 之 Interface / Data Shape：`PlaybookPaneProps` 不變、draft state 不變。驗證方式：新測試 case 出現於 `bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 紅燈列表。
- [x] 1.4 在同檔新增測試「Snapshot disappearance from Diff falls back to Preview」（覆蓋 D2 — `has_previous_version === false` 時 fallback 改為 Preview 的契約）：mock `query.data.has_previous_version` 從 `true` 翻轉成 `false`、且當前 `freeformMode === "diff"`，斷言下一次 render 後 `data-testid="markdown-preview"` 在 DOM、Diff 按鈕從 toggle group 消失。對應 design.md Implementation Contract 之 Failure Modes（snapshot disappear 屬於外部狀態變化下的 fallback path）。驗證方式：新測試出現於 `bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 紅燈列表。
- [x] 1.5 翻轉 / 移除既有測試中假設 mount 後 textarea 直接可見的 assertion（涵蓋 save flow、stale banner、regenerate dialog 路徑）：在所有預期操作 textarea 的測試中，先 `fireEvent.click(getByTestId("freeform-edit-tab"))` 再操作。此 sweep 維持 design.md Implementation Contract 之 Scope Boundaries（只動 freeform 區塊測試、不碰 structured fields tab 與 backend 測試）。驗證方式：`bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 不再出現「unable to find textarea」相關 error；舊 assertion 已全數對齊新 default。

## 2. 綠燈：翻轉 default sub-mode 與 fallback

- [x] 2.1 在 `packages/web/src/components/playbook-pane.tsx` 將 `useState<"edit" | "preview" | "diff">("edit")` 初始值改為 `"preview"`（實作 D1 — 預設 sub-mode 改為 Preview，而非新增第四種模式或 split view）。觀察行為：mount 後 `markdown-preview` 出現於 DOM。驗證方式：Task 1.1 + 1.2 + 1.3 由紅轉綠 (`bun --filter @meeting-playbook/web test playbook-pane.test.tsx` 全綠)。
- [x] 2.2 在 `packages/web/src/components/playbook-pane.tsx` 將 `has_previous_version === false` 時 fallback effect 內 `setFreeformMode("edit")` 改為 `setFreeformMode("preview")`（實作 D2 — `has_previous_version === false` 時 fallback 改為 Preview）。觀察行為：snapshot 從 true 變 false 時、若使用者在 diff，會回到 preview 而非 edit。驗證方式：Task 1.4 由紅轉綠。

## 3. Spec 與 i18n 對齊

- [x] 3.1 確認既有 i18n key `playbook.freeform.previewTab`、`playbook.freeform.editTab`、`playbook.diff.tab` 在 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json` 都已存在（鎖定 D4 — 不引入 user preference 記憶 的決策邊界：本 change 既不新增 preference、也不新增 i18n 字串）。觀察行為：兩個 locale 檔案 deep-equal。驗證方式：`bun --filter @meeting-playbook/web test packages/web/src/locales/locales.test.ts` 全綠（locale parity test）；若任何 key 缺失，先在兩個檔同時補齊。
- [x] 3.2 確認 `packages/web/src/components/playbook-pane.tsx` 仍輸出 `freeform-edit-tab`、`freeform-preview-tab`、`freeform-diff-tab` 三個 `data-testid`（實作 D3 — 既有 testid 與 aria attribute 全部保留 的契約）。觀察行為：DOM 上三個 testid 在 `has_previous_version === true` 時都可被 `getByTestId` 取到；`has_previous_version === false` 時 diff testid 不存在。驗證方式：既有 `playbook-pane.test.tsx` 內 Two / Three sub-mode buttons scenario 測試 全綠。

## 4. 重構與整體驗收

- [x] 4.1 重構：跑 `bun --filter @meeting-playbook/web lint` 並修掉新增的 lint 警告（保持 oxlint 全綠）。觀察行為：lint 0 error 0 warning。驗證方式：lint 指令 exit code 0。
- [x] 4.2 整體 web 測試 sweep：`bun --filter @meeting-playbook/web test` 全綠（涵蓋 playbook-pane.test.tsx + locales.test.ts + 其他可能間接觸發 playbook-pane render 的測試）。此 sweep 滿足 design.md Implementation Contract 之 Acceptance Criteria 全部條目，並驗證 Scope Boundaries 之「Out of scope」清單未被誤動。觀察行為：整個 web 套件無 regression。驗證方式：上述指令 exit code 0。
- [x] 4.3 手動驗收：本地啟動開發服務（root 的 dev script），登入後進入任一既有 meeting detail page，觀察 playbook freeform 區塊預設顯示 rendered markdown（標題大字、bullet 圓點、粗體粗字）；按 Edit tab 後出現 textarea；再按 Preview tab 切回 rendered。觀察行為：對齊 spec MODIFIED requirement「PlaybookPane UI exposes a free-form view, a structured view, and a save action」的全部新 scenario，並驗證 design.md Implementation Contract 之 Behavior 與 Failure Modes（loading / error 狀態下 sub-mode toggle 仍正常）。驗證方式：人工目視 + 截圖確認、回報「OK」。
