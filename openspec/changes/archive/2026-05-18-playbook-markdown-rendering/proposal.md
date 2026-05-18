## Why

Meeting detail page 上的 playbook editor 預設進入 Edit sub-mode，顯示 raw markdown 文字（`#`、`-`、`**` 等符號裸露）。Sean 每次查看 playbook 都要先手動點 Preview tab 才看到 rendered 標題、bullet 與粗體，造成日常閱讀摩擦。Rendered preview 已實作（`MarkdownPreview` + react-markdown + remark-gfm + rehype-sanitize），但因 default mode 設定錯誤，user 大部分時間看到的是不適合閱讀的源碼。本 change 把 freeform sub-mode 的預設值翻轉成 Preview，讓「讀」成為主流程，「寫」成為次流程。

## Summary

Playbook freeform editor 改以 Preview 為預設 sub-mode；user 進入 meeting detail 看到的是 rendered playbook，不是 raw markdown。Edit / Diff 行為與按鈕保留不變。

## Motivation

- 既有 `MarkdownPreview` 已存在於 `packages/web/src/lib/markdown-preview.tsx`，pipeline 完整（remark-gfm + rehype-sanitize），純差在「default mode」上。
- Playbook 是查看 > 編輯的工作流（AI 草稿 + 偶爾微調），預設給 Edit mode 違反實際使用 ratio。
- Diff sub-mode（slice-23 引入）已有自己的 conditional 啟動規則（regenerate 後 auto-switch），不受本 change 影響。

## Proposed Solution

1. 將 `playbook-pane.tsx` 內 `useState<"edit" | "preview" | "diff">("edit")` 的初始值改為 `"preview"`。
2. 更新既有 spec `playbook-management` 的「PlaybookPane UI exposes a free-form view」requirement：將 `**Edit** (default)` 文字改為 `**Preview** (default)`、`**Edit**`（非預設），並調整對應 scenario 以反映 mount 後預設顯示 Preview。
3. 既有 regenerate auto-switch 到 diff、discard 後 fallback 邏輯保留不變；唯一例外：原 `useEffect` 在 `query.data?.has_previous_version === false` 時將 mode 設回 `"edit"` 的 fallback 改為 `"preview"`。
4. 既有 `data-testid="freeform-edit-tab"` / `freeform-preview-tab` / `freeform-diff-tab` 保留不變。`aria-pressed` 在 mount 後預設 Preview 為 true、Edit 為 false。
5. 既有測試 `playbook-pane.test.tsx` 中假設「mount 後 textarea 可見」的 assertion 需翻轉為「mount 後 MarkdownPreview 可見」。涉及 save 流程的測試 path 改為先按 Edit tab、再編輯、再按 Save。
6. 不新增 user-visible 字串；現有 `playbook.freeform.editTab` / `playbook.freeform.previewTab` i18n keys 兩個 locale 都已存在，無 i18n parity 變動。

## Non-Goals

- 不改變 Edit / Preview / Diff 三個 sub-mode 的數量、按鈕、testid。
- 不引入新的 markdown 套件、不變更 react-markdown / remark-gfm / rehype-sanitize 設定。
- 不動 backend（router、schema、repository、Alembic migration 全部不碰）。
- 不引入「點擊 rendered 區塊原地切換成 textarea」的 inline-edit UX——這是更大的設計題，留給後續 change。
- 不調整 Diff sub-mode 在 regenerate 後 auto-switch 的行為。
- 不調整 structured fields tab（六欄結構化編輯器）——本 change 只動 freeform 區塊。

## Alternatives Considered

- **Inline edit（點擊段落變 textarea）**：理想但實作成本高（需 per-block markdown parsing + edit state），且 react-markdown 沒有官方 inline-edit 整合，留給後續 change 評估。
- **Split view（左 raw、右 preview 同畫面）**：在 meeting detail 已是窄欄（playbook pane 寬度有限），split 會兩邊都太擠。已被 slice-7 round 2 評估時拒絕，本 change 不重啟此選項。
- **完全移除 Edit tab、強制 WYSIWYG**：違反「raw markdown 是 source of truth」原則（playbook 來自 Gemini 2.5 Pro 輸出的純 markdown），且失去保險選項。保留 Edit tab 作為「我就是要直接編 raw markdown」的逃生口。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `playbook-management`: 將 PlaybookPane UI requirement 的 freeform sub-mode 預設值從 Edit 改為 Preview，並調整對應 scenarios。

## Impact

- Affected specs:
  - `openspec/specs/playbook-management/spec.md` (MODIFIED requirement: PlaybookPane UI exposes a free-form view, a structured view, and a save action)
- Affected code:
  - Modified:
    - `packages/web/src/components/playbook-pane.tsx` (default `freeformMode` 改為 `"preview"`；`has_previous_version === false` 時 fallback 改為 `"preview"`)
    - `packages/web/src/components/playbook-pane.test.tsx` (mount-time assertions 翻轉；save flow tests 加上「先點 Edit tab」步驟)
  - New: (none)
  - Removed: (none)
- 不影響 backend、auth gateway、Alembic、locale files、其他 capability。
