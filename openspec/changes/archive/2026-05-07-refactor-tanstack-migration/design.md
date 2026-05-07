## Context

slice-01 ~ slice-03 完成後，前端共有 8 條 route（auth shell 5 條、home、meetings 3 條），data fetching 全部走「`useEffect` + `useState` + 手動 setLoading/setError」樣板。home / meetings list / new / detail 各複製一次同樣的 boilerplate；刪 meeting 後 list cache 不會自動失效；route params 沒有 type-safe 機制。

依 ADR 與既有契約：後端 `auth-gateway-contract` 與 `meeting-management` REST 不變，純粹替換前端 routing + data fetching 層。Better Auth 的 `useSession` 是 Better Auth client 內建 hook，與 TanStack Query 解耦，不重寫。

## Goals / Non-Goals

**Goals:**

- 替換 `react-router` v7 → `@tanstack/react-router`（code-based 路由樹）
- 引入 `@tanstack/react-query` v5；list / detail / create / delete 改 hook
- delete mutation 自動 invalidate `["meetings"]`；list 與 detail 不再需要 manual refetch
- `ProtectedShell` 與所有 route 改用 TanStack Router 的 `Navigate` / `Link` / `useNavigate`
- 所有相關 `*.test.tsx` 改用 TanStack Router memory history fixture
- 全 web test suite 仍綠（90+ tests）

**Non-Goals:**

- File-based routing（codegen 會動到 Bun test 設定）
- React Query DevTools
- 後端任何契約改動
- i18n / Better Auth / locale toggle 行為改動
- 重寫 `authClient.useSession`

## Decisions

### Adopt code-based router tree, not file-based

採 `createRootRoute` + `createRoute` 在 `App.tsx` 集中宣告 8 條 route。理由：file-based routing 需要 `@tanstack/router-plugin` 的 Vite codegen，會插入 `routeTree.gen.ts` 並改變 import 路徑；同時可能與 `bun test` 的 happy-dom 啟動序產生 race。code-based 與既有 `BrowserRouter` 用法最接近，搬遷只動 import 不動 file layout。Alternative：file-based routing — 留給未來路由超過 20 條時再評估。

### One QueryClient instance, mounted at app root

`packages/web/src/lib/query-client.ts` export 唯一一個 `QueryClient`，main.tsx 的 `<QueryClientProvider>` 包住整個 App。`staleTime` 預設 0（後續 slice 各自微調）；`refetchOnWindowFocus` 預設關（local-first 桌面工具場景，視窗 focus 不必再打 server）。Test fixture 在每個檔案裡建立獨立 QueryClient，避免 test 之間 cache 污染。

### `lib/meetings-api.ts` 暴露 query options + mutation hooks

保留現有 fetch 函式（`listMeetings` / `getMeeting` / `createMeeting` / `deleteMeeting`），新增：

- `meetingsListQueryOptions()` → `{ queryKey: ["meetings"], queryFn: listMeetings }`
- `meetingQueryOptions(id)` → `{ queryKey: ["meetings", id], queryFn: () => getMeeting(id) }`
- `useCreateMeetingMutation()` → mutationFn: createMeeting；onSuccess invalidate `["meetings"]`
- `useDeleteMeetingMutation()` → mutationFn: deleteMeeting；onSuccess invalidate `["meetings"]` 與 `["meetings", id]`

`MeetingApiError` 仍用 `errorCode` 對應到 `localizedErrorMessage(t)`；query 端透過 `useQuery({ ...options }).error instanceof MeetingApiError` 判斷。

### Test fixture for routed components

統一寫一個 `test/fixtures/router.tsx` helper：

- `renderWithRouter(component, { initialEntries })` — 內部建一個臨時 `createRouter({ routeTree, history: createMemoryHistory({ initialEntries }) })` 並用 `<RouterProvider>` 包住；同時建立獨立 `QueryClient` 跟 `<QueryClientProvider>` 包住。
- 既有 `MemoryRouter` 用法移除。
- `useNavigate` mock：在 mutation 成功 redirect 的測試裡，改檢查 router 的 `state.location.pathname` 是否等於預期 path。

### `ProtectedShell` 改用 TanStack Router

`useNavigate` → `useNavigate({ from: ... })` 或 router-level `navigate({ to })`；`<Link to="/meetings">` 維持類似 API；`replace: true` 改成 `replace: true` option。session 檢查邏輯不變。

### 移除 `react-router` 依賴

`bun remove react-router`；同步移除所有 `import { ... } from "react-router"`。

## Risks / Trade-offs

- [Risk] TanStack Router 的型別系統較嚴，全 route tree 需重新標 `Route.params` 與 `validateSearch`，初期可能寫得比現在多 → Mitigation：先以最小可運作為目標，型別嚴格度後續逐步提升
- [Risk] Bun test 與 TanStack Router 的 `@tanstack/router-devtools` 可能有 DOM 相容性問題 → Mitigation：dev 期不引入 devtools；測試用 memory history 而非 BrowserRouter
- [Risk] 既有 `*.test.tsx` 改寫量大（10+ files），可能漏改某些 mock → Mitigation：分頁面 vertical slice 改寫，每個檔案改完跑該檔測試確認綠再下一個
- [Risk] `react-router` v7 的 `Navigate` component 在 TanStack Router 沒有 1:1 對應 → Mitigation：改成 route-level redirect 或 `useEffect` + `navigate({ to, replace: true })`
- [Trade-off] 不上 file-based routing 會犧牲未來自動產生 type-safe 路徑的便利；但不上 codegen 顯著降低本次改寫風險

## Migration Plan

1. 在 `packages/web` 安裝 `@tanstack/react-router` 與 `@tanstack/react-query`，移除 `react-router`
2. 建立 `lib/query-client.ts` 與 `test/fixtures/router.tsx`
3. 改寫 `App.tsx` 為 TanStack Router code-based route tree
4. 改寫 `lib/meetings-api.ts` 加入 query options 與 mutation hooks
5. 逐頁改：home → meetings list → meetings new → meetings detail → ProtectedShell → login → signup → totp/enroll → totp/verify
6. 每頁同步改對應 `*.test.tsx`，跑該檔 test 確認綠
7. 全 web suite + auth suite + backend suite 全綠後 propose archive

回滾策略：`git revert` 整批 commit；refactor 不動 spec 不動後端，回滾單純。

## Open Questions

- 是否需要把 `home.tsx` 也改用 TanStack Query？home 目前 fetch `/api/me` 的部分仍是 boilerplate。決議：是。一併改。
- query stale time 預設多少？決議：`staleTime: 0`，後續 slice 各自微調（meeting list 可拉長到 30s）。
- mutation onError 是否要 toast？目前 UI 只在 page-level alert 顯示 error。決議：不上 toast（Slice 4+ 再評估）；維持 page-level alert。
