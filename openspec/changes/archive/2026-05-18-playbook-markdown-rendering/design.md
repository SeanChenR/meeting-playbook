## Context

`packages/web/src/components/playbook-pane.tsx` 目前以 `useState<"edit" | "preview" | "diff">("edit")` 初始化 freeform sub-mode，user 進入 meeting detail 看到的是 raw markdown textarea。Rendered preview 機制（`packages/web/src/lib/markdown-preview.tsx`，react-markdown + remark-gfm + rehype-sanitize）已存在且運作正常——本 change 純粹反轉預設值與調整相應 fallback。

相關歷史脈絡：
- Slice-7 round 2 引入 freeform Edit / Preview sub-toggle，當時為了 backward-compat 與保險選擇 Edit 為 default。
- Slice-23 為 playbook-versioning 加上 Diff sub-mode（conditional render，當 `has_previous_version === true` 才顯示按鈕，且 regenerate 後 auto-switch）。Diff 行為與本 change 正交，不需動。
- Project memory `project_playbook_markdown_rendering_deferred.md` 標註本題目原本 deferred；現於 mixed-stream-playback 之外獨立 land。

## Goals / Non-Goals

**Goals:**
- 進入 meeting detail page 後，playbook freeform 區塊預設顯示 rendered markdown（`MarkdownPreview` 元件已實作的 prose 樣式：標題、bullet、粗體、表格、code block）。
- 「想要編輯 raw markdown」的逃生口仍存在：點擊既有 Edit sub-tab 按鈕即可切到 textarea。
- 既有所有 testid、aria attribute、i18n key 不變；外部測試與 e2e 自動化只需更新「mount 後 default mode」相關 assertion。
- Diff sub-mode 的 auto-switch（regenerate 後）與 conditional render（has_previous_version）行為完全保留。

**Non-Goals:**
- 不引入 inline edit（點 rendered 段落原地變 textarea）。
- 不引入 split view（左 raw、右 preview 同畫面）。
- 不變更 react-markdown / remark-gfm / rehype-sanitize 任何配置。
- 不動 backend、schema、Alembic、Better Auth、auth gateway。
- 不變更 structured fields tab（6 個結構化欄位）的行為。
- 不調整 save / regenerate / discard / restore mutation 邏輯。
- 不引入「user 偏好記憶」（記住 user 上次選的 sub-mode）——預設恆為 preview。

## Decisions

### D1 — 預設 sub-mode 改為 Preview，而非新增第四種模式或 split view

`useState<"edit" | "preview" | "diff">("preview")`。

**為什麼這樣選**：
- Playbook 的使用比例壓倒性偏向「讀」（每次打開 meeting detail 都會看，但只有微調或新增 talking point 時才會編輯）。
- Preview 已被 react-markdown + remark-gfm + rehype-sanitize 完整實作，沒有新引入 surface area。
- 改一個 string literal（從 `"edit"` 到 `"preview"`）的 blast radius 最小，且 Edit tab 仍然存在，沒有功能損失。

**Alternative considered**：
- Split view（左 raw / 右 preview）：playbook pane 在 meeting detail 是窄欄，slice-7 round 2 已拒絕此方案。
- Inline edit（點段落原地變 textarea）：需要 per-block markdown parsing 與額外 state，是新 surface area。留給後續 change。
- Toggle 預設記憶 user 上次選擇：新增 localStorage / preference 表，且第一次 mount 仍要決定 default——直接固定 default 更乾淨。

### D2 — `has_previous_version === false` 時 fallback 改為 Preview

既有程式碼有此 effect：

```
if (freeformMode === "diff" && query.data && !query.data.has_previous_version) {
  setFreeformMode("edit");
}
```

改為 `setFreeformMode("preview")`。

**為什麼這樣選**：
- 「snapshot 消失了，要把 user 從 diff 模式踢回去」的目的地應該與 default mount 一致；現在 default 是 preview，fallback 也該是 preview。

**Alternative considered**：
- 保留 fallback 為 edit、只改 mount default：行為不一致（mount 後在 preview，但 snapshot 消失後突然跳 edit），會困惑 user。

### D3 — 既有 testid 與 aria attribute 全部保留

`freeform-edit-tab` / `freeform-preview-tab` / `freeform-diff-tab` 三個 testid 不變；`aria-pressed` 對應 `freeformMode === "preview"` 為 true（mount 時）。

**為什麼這樣選**：
- e2e 測試（如 capture-flow.spec.ts 等）若有引用這些 testid，可以無痛通過。
- Accessibility tree 邏輯不變，只是 mount 後 active button 從 Edit 變 Preview。

**Alternative considered**：
- 將 Edit / Preview 兩個按鈕合併成單一 toggle switch：UI 變動較大、需要新 i18n string、且不必要。

### D4 — 不引入 user preference 記憶

預設恆為 Preview，不寫入 localStorage、不持久化 user 上次選的 sub-mode。

**為什麼這樣選**：
- 單一 user (Sean)、單機 macOS，預設行為對齊正確使用情境就夠。
- 引入 preference 表會擴大 surface area（哪個 scope？per-meeting？global？跨裝置怎麼辦？）。

**Alternative considered**：
- localStorage 記憶 last selected sub-mode：增加 state 來源，且首次進入 meeting 仍要決定 default，不解決問題。

### D5 — 測試策略：翻轉既有 mount-time assertion，新增「點 Edit 才看到 textarea」path

`packages/web/src/components/playbook-pane.test.tsx` 內既有測試假設：
- Mount 後 textarea 直接 visible → 翻轉成「mount 後 `<MarkdownPreview>` (data-testid `markdown-preview`) visible，textarea 不在 DOM」。
- Save flow 測試直接 `fireEvent.change(textarea, ...)` → 改為先 `fireEvent.click(getByTestId("freeform-edit-tab"))`、再操作 textarea、再按 Save。

**為什麼這樣選**：
- 測試對齊 user 實際操作流程（先切到 Edit、再編輯、再 Save）。
- 不需新增 mock，無 surface area 增加。

**Alternative considered**：
- 加 `defaultMode` prop 讓測試傳 `"edit"`：增加 component API 表面積、且需要新測試覆蓋 prop 行為。本 change 不值得。

## Implementation Contract

### Behavior

- **Observable**：user 進入 `/meetings/<id>` 後，playbook pane 內 freeform 區塊預設顯示 rendered markdown（標題為大字、bullet 為圓點、粗體為粗體字、表格為 HTML table、code block 為等寬字背景灰）。
- **Edit toggle**：點擊 `freeform-edit-tab` 按鈕後，rendered preview 消失、textarea 出現、user 可編輯 raw markdown。再次點 `freeform-preview-tab` 切回 rendered。
- **Diff toggle**（unchanged）：只有當 `query.data?.has_previous_version === true` 才出現第三顆按鈕；regenerate 後若新舊內容不同，sub-mode auto-switch 到 `"diff"`；snapshot 消失後 fallback 到 `"preview"`（D2）。
- **Save flow**：只在 Edit sub-mode 顯示 Save button 之 textarea；切到 Preview 時 Save button 仍可見（不變），但因為沒在編輯，按下 Save 等於 save 當前 draft state（與 Edit 一致）。
- **Regenerate stale banner**：行為不變。

### Interface / Data Shape

- 不新增、不變更 component prop。`PlaybookPaneProps` 仍為 `{ meetingId: string }`。
- 不新增、不變更 i18n key。`playbook.freeform.editTab` / `playbook.freeform.previewTab` / `playbook.diff.tab` 三個 key 在 `zh-TW.json` 與 `en.json` 已存在。
- 不新增、不變更 backend API、TanStack Query key、mutation payload。

### Failure Modes

- 若 query loading（`query.isLoading === true`），保持原本 loading text；sub-mode 預設值不影響。
- 若 query error，原本的 Alert 樣式保留；sub-mode toggle 仍渲染（保留 D3 testid）。
- 若 `query.data.free_form_markdown` 為空字串，`<MarkdownPreview source="" />` 渲染為空 prose div（既有行為）；user 仍可點 Edit 進去輸入。

### Acceptance Criteria

- `bun --filter @meeting-playbook/web test packages/web/src/components/playbook-pane.test.tsx` 全綠，且新增/修改的 assertion 涵蓋：
  - Mount 後 `<MarkdownPreview>` (testid `markdown-preview`) 出現、textarea 不在 DOM。
  - 點 `freeform-edit-tab` 後 textarea 出現、`<MarkdownPreview>` 不在 DOM。
  - 點 `freeform-preview-tab` 後又切回 `<MarkdownPreview>`。
  - `freeformMode` initial render 為 preview 時，`freeform-preview-tab` 的 `aria-pressed` 為 `"true"`、`freeform-edit-tab` 為 `"false"`。
  - 當 `has_previous_version === true` 時三顆按鈕都 render；當 `has_previous_version === false` 時只有兩顆。
  - Regenerate 後 auto-switch 到 diff 的既有測試仍綠。
  - Snapshot 消失後 fallback 到 preview（不是 edit）。
- `bun --filter @meeting-playbook/web lint` 通過、`bun --filter @meeting-playbook/web test` 全綠。
- 既有 e2e（若有引用 playbook pane）不需更動，因為 testid 與 button 數量不變。

### Scope Boundaries

**In scope**:
- `packages/web/src/components/playbook-pane.tsx` 第 ~61 行 `useState` 初始值。
- `packages/web/src/components/playbook-pane.tsx` 第 ~104-108 行 fallback effect 的 `setFreeformMode("edit")` 改為 `"preview"`。
- `packages/web/src/components/playbook-pane.test.tsx` 對應 assertion 翻轉。
- `openspec/specs/playbook-management/spec.md` 對應 requirement 與 scenarios 更新。

**Out of scope**:
- 任何 backend / schema / repository / router 變動。
- `playbook-pane.tsx` 內 save / regenerate / discard / restore mutation 邏輯。
- `MarkdownPreview` 元件本身（react-markdown plugin、sanitize 設定、prose className）。
- Structured fields tab。
- i18n locale files。
- 其他 capability 的 spec。
- User preference persistence（D4）。
- Inline edit / split view（D1）。

## Risks / Trade-offs

- **Risk**：user 把舊的肌肉記憶（mount 後直接打字）帶過來，第一次發現要先點 Edit 會困惑。
  - **Mitigation**：Edit tab 按鈕 prominent、文字明確（`playbook.freeform.editTab` 已是「編輯」）；hover 即可看到狀態。單一 user 場景下，第一次切換成本可接受。
- **Risk**：既有快照測試（snapshot test）若有引用 `<textarea>` 為 default render output，會 fail。
  - **Mitigation**：本 codebase 未使用 Jest snapshot 風格的 component snapshot，行為驅動測試會被 D5 task 顯式更新。
- **Risk**：未來若引入 inline edit，可能要再次調整 default mode 邏輯。
  - **Mitigation**：D4 不引入 preference 持久化，現在的決策容易再次 invert；新增 mode 也只是擴 enum union。
- **Trade-off**：固定 default 為 preview 喪失「user 偏好」彈性。接受——對齊單一 user 真實使用比例。
