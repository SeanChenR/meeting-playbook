## 1. Dependencies and infrastructure (covers "移除 `react-router` 依賴" and "One QueryClient instance, mounted at app root")

- [x] 1.1 Action for "移除 `react-router` 依賴": in `packages/web` run `bun add @tanstack/react-router @tanstack/react-query` and `bun remove react-router`; commit `package.json` and `bun.lock` changes.
- [x] 1.2 Action for "One QueryClient instance, mounted at app root": create `packages/web/src/lib/query-client.ts` exporting a single `QueryClient` (staleTime=0, refetchOnWindowFocus=false); add unit test `query-client.test.ts` asserting default options (red → green).
- [x] 1.3 Wrap `<App />` in `packages/web/src/main.tsx` with `<QueryClientProvider client={queryClient}>` to land the "One QueryClient instance, mounted at app root" decision at entry; preserve the existing i18n side-effect import; add an i18n-bootstrap-style test that confirms `main` still boots correctly.

## 2. Test fixture for routed components

- [x] 2.1 [P] Action for "Test fixture for routed components": create `packages/web/src/test/fixtures/router.tsx` exporting `renderWithRouter(component, { initialEntries })`; internally build an ad-hoc `createRouter({ routeTree, history: createMemoryHistory({ initialEntries }) })` plus a fresh `QueryClient`, wrapped in `<QueryClientProvider>` and `<RouterProvider>`; ship a minimal `router-fixture.test.tsx` that renders a `<div>` to prove the fixture works.

## 3. App.tsx swap (covers "Adopt code-based router tree, not file-based")

- [x] 3.1 Action for "Adopt code-based router tree, not file-based": rewrite `packages/web/src/App.tsx` using `createRootRoute` and `createRoute` to declare the eight routes (`/login`, `/signup`, `/totp/enroll`, `/totp/verify`, `/home`, `/meetings`, `/meetings/new`, `/meetings/:id`); root `/` redirects to `/meetings`; export a single `router` instance; reuse the existing `App.test.tsx` smoke test (let it fail first, turn green after rewrite).
- [x] 3.2 [P] Remove `BrowserRouter` and any other `react-router` import lingering anywhere in `packages/web/src`; confirm clean via `bun run lint` (`oxlint`).

## 4. `lib/meetings-api.ts` query options + mutation hooks (covers "`lib/meetings-api.ts` 暴露 query options + mutation hooks")

- [x] 4.1 [AC-4] Action for "`lib/meetings-api.ts` 暴露 query options + mutation hooks" (queries half): add `meetingsListQueryOptions()` and `meetingQueryOptions(id)` with unit test `meetings-api.queries.test.ts` asserting correct `queryKey` and `queryFn` behaviour; implement to green.
- [x] 4.2 [AC-4] Action for "`lib/meetings-api.ts` 暴露 query options + mutation hooks" (mutations half): add `useCreateMeetingMutation` and `useDeleteMeetingMutation`; test `meetings-api.mutations.test.tsx` uses `renderHook` with a `QueryClientProvider` to verify that on success `["meetings"]` and `["meetings", id]` are invalidated; implement to green.

## 5. Page rewrites (vertical: each page ships its own test rewrite)

- [x] 5.1 [AC-5][AC-6] Rewrite `routes/meetings/list.tsx` to consume `useQuery(meetingsListQueryOptions())`; remove the `useEffect+useState` boilerplate; rewrite `list.test.tsx` to use `renderWithRouter`; add a "after delete the list refetches" assertion.
- [x] 5.2 [AC-4][AC-6] Rewrite `routes/meetings/new.tsx` around `useCreateMeetingMutation`; on success `useNavigate` to `/meetings/:id`; rewrite `new.test.tsx` accordingly.
- [x] 5.3 [AC-7][AC-8] Rewrite `routes/meetings/detail.tsx` around `useQuery(meetingQueryOptions(id))` + `useDeleteMeetingMutation`; rewrite `detail.test.tsx`; assert that delete invalidates list cache.
- [x] 5.4 Rewrite `routes/home.tsx` so `/api/me` and `listAccounts` go through `useQuery`; rewrite `home.test.tsx`; confirm backend confirmation card and security card behaviour are unchanged.

## 6. ProtectedShell and auth flows on TanStack Router (covers "`ProtectedShell` 改用 TanStack Router")

- [x] 6.1 [AC-6] Action for "`ProtectedShell` 改用 TanStack Router": rewrite `components/protected-shell.tsx` to use TanStack Router's `useNavigate` and `<Link>`; verify logout and unauthenticated redirect behaviour are unchanged.
- [x] 6.2 [P] [AC-3] Rewrite `routes/login.tsx` navigation to TanStack Router; keep the `callbackURL` string at `/meetings`; update `login.test.tsx` and `login-i18n.test.tsx`.
- [x] 6.3 [P] [AC-3] Rewrite `routes/signup.tsx` navigation to TanStack Router; update `signup.test.tsx`.
- [x] 6.4 [P] [AC-3] Rewrite `routes/totp/enroll.tsx` navigation to TanStack Router; update any related test.
- [x] 6.5 [P] [AC-3] Rewrite `routes/totp/verify.tsx` navigation to TanStack Router; update any related test.

## 7. Wrap-up

- [x] 7.1 [AC-1] Confirm `packages/web/package.json` no longer lists `react-router` and now lists `@tanstack/react-router` + `@tanstack/react-query`; run `bun install` so `bun.lock` is consistent.
- [x] 7.2 [AC-9] Run the full `bun --filter @meeting-playbook/web test` suite (90+ tests all green); confirm auth + backend suites remain green.
- [x] 7.3 Manual smoke test (in tmux): login → /meetings (list) → /meetings/new → create → automatic redirect to /meetings/:id → delete → automatic return to /meetings showing the list refetched (no manual reload); switch to EN locale and confirm every route still translates.
- [x] 7.4 Verify all acceptance criteria from issue #15 are checked off in GitHub Issue.
