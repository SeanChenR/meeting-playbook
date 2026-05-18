# UI Overhaul — 決策 worksheet

> 用法：把要選的選項打勾 `[x]`，「其他」欄位直接寫文字。填完回到 chat 跟我說「填好了」我就接手做 `/spectra-propose ui-overhaul-aura-theme`。
>
> 目的：把 26 個 slice 拼成的當前 UI，整體換到 Aura theme + 重新組織 IA + 升級 layout primitives。

---

## Context（給你參考用，不用填）

### Theme 基準

**錨點**：[daltonmenezes/aura-theme](https://github.com/daltonmenezes/aura-theme)
**模式**：dark 為基準，light 用 Aura `*-soft` 變體鏡像對折
**鐵律**：不要死黑（`#15141b` 已是略紫的近黑）、不要死白（`#edecee` 已是略紫的近白）、無 emoji、所有 color 走 `oklch()` CSS variable

#### Aura 原色 → 專案 token mapping

| Role | Aura Hex | Dark token (oklch 近似) | Light token (oklch 近似) |
|---|---|---|---|
| background | `#15141b` / `#edecee` | `0.17 0.015 290` | `0.97 0.003 295` |
| surface | — | `0.22 0.015 290` | `1.00 0 0` |
| foreground | `#edecee` / `#15141b` | `0.93 0.003 295` | `0.20 0.015 290` |
| primary (purple) | `#a277ff` / `#8464c6` | `0.65 0.22 290` | `0.50 0.18 290` (soft) |
| secondary / success (green) | `#61ffca` / `#54c59f` | `0.91 0.18 165` | `0.65 0.13 165` (soft) |
| warning (orange) | `#ffca85` / `#c7a06f` | `0.86 0.13 75` | `0.72 0.11 75` (soft) |
| danger (red) | `#ff6767` / `#c55858` | `0.70 0.22 25` | `0.58 0.18 25` (soft) |
| me (我方 — blue) | `#82e2ff` / `#6cb2c7` | `0.86 0.12 220` | `0.65 0.10 220` (soft) |
| them (對方 — pink) | `#f694ff` / `#c17ac8` | `0.77 0.22 320` | `0.55 0.15 320` (soft) |
| muted (gray) | `#6d6d6d` | `0.5 0 0` | `0.5 0 0` |

規則：light = `*-soft` 變體（飽和低、白底不刺眼）；dark = vibrant 原色。

#### 非 color token

| Token | 動作 | 備註 |
|---|---|---|
| `--font-sans` Inter + Noto Sans TC | 不動 | 中英對齊已驗 |
| `--font-mono` JetBrains Mono | 不動 | |
| `--text-*` scale + density | 不動 | |
| `--space-*` 4/8/12/16/24/32/48 | 不動 | 8pt grid 成熟 |
| `--radius-*` | 見 B3 | |
| `--shadow-*` | 見 B4 | |
| 動畫 `mp-pulse/fade-in/shimmer` | 不動 | 與主題正交 |

### 現況 routing（受保護區）

```
/                         Dashboard
/meetings                 Meetings list（Kanban / Calendar / List）
/meetings/new             建會
/meetings/:id             Detail（全站最複雜頁）
/calendar/upcoming        Calendar — 另一個獨立頁
/settings/profile         個人
/settings/security        2FA
/settings/preferences     偏好
/settings/data            匯出/刪除
/settings/integrations    第三方
/settings/voice           聲紋（meeting-scoped）
/settings/tags            標籤（meeting-scoped）
```

### Meeting Detail 三個 Layout 提案

**提案 1 — Tabbed Workspace（保守）**
```
MetadataCard slim
Tabs: Transcript | Playbook | Summary | Advisor
└─ 單欄全寬 surface
Sticky bottom mini player
```
✅ 每 surface 全寬好讀；mini player 一直在
❌ 跨 surface 切換要 click tab

**提案 2 — 主從雙欄（中庸）**
```
MetadataCard slim
┌────────────────┬──────────────┐
│ Primary 60%    │ Secondary 40%│
│ Transcript     │ - Advisor    │
│  or Playbook   │ - Summary    │
│ (toggle 主軸)  │ - Attach     │
└────────────────┴──────────────┘
Sticky bottom mini player
```
✅ 主面寬、輔助常駐
❌ 13" 仍稍擠

**提案 3 — Focus Mode（激進）**
```
小 status bar
┌────────────────────────────┐
│                            │
│   單一 surface 占滿        │
│   (transcript/playbook/    │
│    summary/advisor)        │
│                            │
└────────────────────────────┘
Floating mini player + surface switcher
```
✅ 沉浸感像 Linear / Things
❌ 切換靠 muscle memory

---

# ✍️ 填答區

## Theme

### B1. Speaker me/them 配色
- [同意] 接受 blue(我方) / pink(對方)
- [同意] 保留同 hue 不同飽和度
- [同意] 其他：是連其他相關 Component 都要換成該主題的配色！

### B2. Light mode 用 Aura `*-soft` 變體當 accent
- [同意] 接受
- [ ] 不接受，改用：______

### B3. Radius 規格
- [同意] sharp (4/6/8)
- [同意] 保留 (4/8/12)
- [ ] 其他：______

### B4. Shadow 改寫方向（dark 幾乎無 shadow、light 留淡 shadow）
- [同意] 接受
- [ ] 其他：______

---

## IA（資訊架構）

### A1. `/calendar/upcoming` 怎麼處理
- [同意] 合併到 `/meetings?view=calendar`，砍掉
- [ ] 保留但重新分工（說明：______）
- [ ] 其他：______

### A2. Dashboard 定位
- [ ] 改成 hub（近期 meeting + 未讀 playbook + recording 倒數 + tag 摘要）
- [ ] 改成 summary（單純會議統計）
- [同意] 其他：Dashboard 維持現狀這樣就好。

### A3. Settings 結構

這個具體不太懂什麼意思，Account vs Workspace 拆完會變成怎麼樣？

- [ ] 拆 Account vs Workspace
- [ ] 保持 7 個並列
- [ ] 其他：______

### A4. `/recordings` 新增獨立入口
- [同意] 加（30 天 window 索引 + 搜尋 + 批量下載）
- [ ] 不加
- [ ] 加但範圍縮小（說明：______）

---

## Layout

### C1. Meeting detail 選哪個
- [ ] 提案 1 Tabbed Workspace
- [ ] 提案 2 主從雙欄
- [ ] 提案 3 Focus Mode
- [同意] 都不要，我想要：這頁的內容我們另外拉出來討論

### C2. Mini player 位置
- [ ] sticky bottom（提案 1/2 預設）
- [ ] floating（提案 3 預設）
- [同意] 其他：維持現狀

---

## 自由補充

我還想加 / 改 / 不要做的：

```
有開啟 Dialog 的套用：https://animate-ui.com/docs/components/base/dialog

逐字稿的選單採用：https://animate-ui.com/docs/components/base/popover

上傳或請 AI 產生摘要或做什麼進程，採用 https://animate-ui.com/docs/components/base/progress 進度條，如果沒辦法準確估算進度，

深色背景可加入：https://animate-ui.com/docs/components/backgrounds/stars 這種 background，套用於每個分頁

深淺主題切換直接套用：https://magicui.design/docs/components/animated-theme-toggler，不要再用現在這樣的下拉選單

hover 可以顯示補充資訊的，都加入 tooltip：https://animate-ui.com/docs/primitives/animate/tooltip

建立和編輯選擇日期的選擇：https://www.shadcnblocks.com/component/calendar/calendar-standard-3

在會議中可以用 https://ui.elevenlabs.io/docs/components/bar-visualizer，Connecting 可能代表還在下載 Model，然後開始的時候就可以用 Speaking 和 Listening 來顯示是誰在講話，雖然不一定精準，但畢竟我們有用雙聲道、單聲道等等，都是可以嘗試的吧。

https://ui.elevenlabs.io/docs/components/transcript-viewer 這個可以搭配逐字稿那邊！

按鈕 hover 動畫可以參考：https://uiverse.io/adamgiebl/pink-chicken-70，但配色還是照我們的配色。

逐字稿那邊是不是可以：https://magicui.design/docs/components/animated-list 這樣顯示出來

很多卡片的元件 hover 可以加入：https://uiverse.io/Tiagoadag/cuddly-catfish-6

按鈕下去該跑進度的跑進度，該顯示完成的用 https://ui.devsloka.in/components/success-result

input 框框可以套用：https://uiverse.io/Lakshay-art/curvy-earwig-22，但是改成我們自己的主題配色風格。

https://uiverse.io/Smit-Prajapati/spicy-rat-83 這個效果不錯可以想一下要套用在哪。

https://www.vengenceui.com/docs/glass-dock Dock 可以想想可以用在哪。

最後多善用 Toast，記得 info 藍色、error 紅色、warning 黃色、success 綠色，然後有什麼不知道需要我補充的再來問我。
```

---

## 重構執行策略（我的建議，你也可以否決）

這量級不適合單一 change。建議拆三段，依序進行：

1. **`ui-overhaul-aura-tokens`** — 純 token 層替換（`index.css` + 任何 hardcoded color），不動 layout / IA。最小破壞性，PR 容易 review。
2. **`ui-overhaul-ia-refactor`** — 動 routing、navigation、page 重組（A1 / A2 / A3 / A4）。
3. **`ui-overhaul-meeting-detail-layout`** — Meeting detail 三選一的 layout 改造（C1 / C2），加上其他頁面的 layout primitive 升級。

要不要照這個順序？

- [ ] 接受三段拆分
- [同意] 全部塞一個 change
- [ ] 我想這樣拆：______
