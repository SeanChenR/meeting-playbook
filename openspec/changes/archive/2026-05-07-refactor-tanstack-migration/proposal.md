GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/15

## Why

slice-01~03 累積了 React Router 7 + 手寫 `useEffect+useState` fetch 的樣板（home / meetings list / new / detail 各重一次），刪除 meeting 後 list 不會自動 refetch、route 沒有 type-safe params 也沒有 loader pattern。後續 6+ 條 vertical slice（transcripts / playbook / advisor / summary…）將沿用同一套樣板；現在換成本最小，越拖越貴。

## What Changes

- **BREAKING**：`react-router` v7 → `@tanstack/react-router`（code-based 路由樹，不上 file-based 以保留 Bun test 設定）
- 新增 `@tanstack/react-query` v5；`QueryClientProvider` 掛在 app root
- `lib/meetings-api.ts` 暴露 `meetingsListQueryOptions` / `meetingQueryOptions(id)` 與 mutation hooks（`useCreateMeetingMutation` / `useDeleteMeetingMutation`），delete 自動 invalidate `["meetings"]`
- list / new / detail / home 全部改用 `useQuery` / `useMutation`，移除 `useEffect+useState` fetch 樣板
- `ProtectedShell` 與所有 route 改用 TanStack Router 的 `Navigate` / `Link` / `useNavigate` API
- 所有受影響的 `*.test.tsx` 重寫：`MemoryRouter` → TanStack Router 的 `createMemoryHistory` + `RouterProvider` fixture

## Non-Goals

- 不上 file-based routing（codegen 會動到 Bun test 設定，留作未來）
- 不引入 React Query DevTools
- 不動後端契約（`auth-gateway-contract` 與 `meeting-management` spec 不變）
- 不動 i18n、Better Auth、locale toggle 流程
- 不動 mobile / Tauri shell

## Capabilities

### New Capabilities

(無)

### Modified Capabilities

(無) — 純前端 refactor，spec 行為不變。

## Impact

- 新增依賴：`@tanstack/react-router`、`@tanstack/react-query`
- 移除依賴：`react-router`
- 修改：
  - `packages/web/package.json`
  - `packages/web/src/main.tsx`
  - `packages/web/src/App.tsx`
  - `packages/web/src/lib/meetings-api.ts`
  - `packages/web/src/components/protected-shell.tsx`
  - `packages/web/src/routes/login.tsx`
  - `packages/web/src/routes/signup.tsx`
  - `packages/web/src/routes/home.tsx`
  - `packages/web/src/routes/totp/enroll.tsx`
  - `packages/web/src/routes/totp/verify.tsx`
  - `packages/web/src/routes/meetings/list.tsx`
  - `packages/web/src/routes/meetings/new.tsx`
  - `packages/web/src/routes/meetings/detail.tsx`
  - 對應 `*.test.tsx`（router context fixture 改寫）
- 不動：`packages/auth/`、`packages/backend/`、`openspec/specs/`、所有 i18n locale json
