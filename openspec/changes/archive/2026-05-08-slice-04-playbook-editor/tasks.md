## 1. Schema and migration (covers "Alembic migration: playbook table schema" and Requirement: "Each meeting has at most one playbook scoped to that meeting")

- [x] 1.1 [AC-1] Action for "Alembic migration: playbook table schema" + Requirement: "Each meeting has at most one playbook scoped to that meeting" (RED): write `tests/test_alembic_playbook.py` to verify the `playbook` table has the seven content columns plus `meeting_id`, `created_at`, `updated_at`; UNIQUE(meeting_id); FK on `meeting_id` ON DELETE CASCADE; assert that inserting a second playbook for the same meeting violates the UNIQUE constraint.
- [x] 1.2 [AC-1] Action for "Alembic migration: playbook table schema" (GREEN): create `packages/backend/alembic/versions/0002_create_playbook.py` matching the schema; verify `alembic upgrade head` then `alembic downgrade -1` is reversible against the test DB.
- [x] 1.3 Update `packages/backend/tests/conftest.py` so per-test teardown also `TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE` to keep slice-04 tests isolated. (Covers the slice-wide test discipline laid out in the design's "Test strategy (TDD vertical slice)" section: every spec is exercised end-to-end through repository / endpoint / component layers, and a leaking row would invalidate the strategy.)

## 2. PlaybookRepository (covers "PlaybookRepository (async SQLAlchemy 2.0) as the single access path")

- [x] 2.1 [AC-1][AC-3] Action for "PlaybookRepository (async SQLAlchemy 2.0) as the single access path" (RED): add `tests/playbooks/test_repository.py` with cases for `get_or_create_for_meeting` (first call inserts empty row; second call returns same id) and `upsert_for_meeting` (full replacement of the seven content fields, `updated_at` advances).
- [x] 2.2 [AC-1][AC-3][AC-4] Add `packages/backend/meeting_playbook/playbooks/{__init__,models,repository}.py`; implement both methods using `INSERT ... ON CONFLICT (meeting_id) DO ...` so 2.1 turns green.
- [x] 2.3 [AC-5] [P] Covers Requirement: "Playbook content fields accept arbitrary markdown including Chinese-English mix". Extend `tests/playbooks/test_repository.py` with a Chinese-English mixed markdown round-trip case (60+ line `free_form_markdown` plus emoji and headings) — fields persist byte-for-byte.

## 3. FastAPI router with ownership gate (covers "FastAPI router with ownership gate via MeetingRepository")

- [x] 3.1 [AC-2] Action for "FastAPI router with ownership gate via MeetingRepository" + Requirements: "Playbook access is gated by meeting ownership" and "GET auto-creates an empty playbook on first read" (RED): add `tests/playbooks/test_endpoints.py` covering owner GET (first read auto-creates with all seven fields equal to empty string; second read returns the same playbook id), owner PUT (full upsert), cross-user GET → 404 + `error_code: meeting.not_found`, cross-user PUT → 404 + playbook unchanged.
- [x] 3.2 [AC-2][AC-3][AC-4] Add `packages/backend/meeting_playbook/playbooks/{schemas,router}.py`; mount the router in `packages/backend/meeting_playbook/server.py`; both endpoints first call `MeetingRepository.get_for_user`, then delegate to `PlaybookRepository`. 3.1 turns green.
- [x] 3.3 [AC-4] [P] Covers Requirement: "PUT performs a full upsert with seven content fields". Add `tests/playbooks/test_validation.py` parametrized with the spec example matrix (rows: `{"objective":"X","red_lines":"Y"}` → both set, `{"objective":"X"}` → red_lines becomes empty string, `{}` → all fields become empty string), plus a 10K-character `free_form_markdown` round-trip and a `updated_at` advances assertion across two consecutive PUTs.

## 4. Frontend — playbook-api lib (covers "`lib/playbook-api.ts` query options + mutation hook")

- [x] 4.1 [AC-2][AC-4] Action for "`lib/playbook-api.ts` query options + mutation hook" (queries half, RED): add `packages/web/src/lib/playbook-api.queries.test.ts` covering `playbookQueryOptions(meetingId)` (queryKey `["playbook", meetingId]`, queryFn calls `GET /api/meetings/:id/playbook` and returns the JSON) and `getPlaybook` / `upsertPlaybook` raising a `PlaybookApiError` with `errorCode` on non-2xx.
- [x] 4.2 [AC-2][AC-4] Add `packages/web/src/lib/playbook-api.ts` (fetch wrappers + `PlaybookApiError` + `playbookQueryOptions`); 4.1 turns green.
- [x] 4.3 [AC-4] Action for "`lib/playbook-api.ts` query options + mutation hook" (mutations half, RED): add `packages/web/src/lib/playbook-api.mutations.test.tsx` using `renderHook` + `QueryClientProvider` to verify `useUpsertPlaybookMutation(meetingId)` invalidates `["playbook", meetingId]` on success.
- [x] 4.4 [AC-4] Implement `useUpsertPlaybookMutation` in `playbook-api.ts`; 4.3 turns green.

## 5. Frontend — PlaybookPane component (covers "PlaybookPane React component with view-mode toggle" and Requirement: "PlaybookPane UI exposes a free-form view, a structured view, and a save action")

- [x] 5.1 [AC-6][AC-7] Action for "PlaybookPane React component with view-mode toggle" + Requirement: "PlaybookPane UI exposes a free-form view, a structured view, and a save action" (RED, view + content): add `packages/web/src/components/playbook-pane.test.tsx` covering "renders free-form textarea by default", "toggle reveals six labeled structured fields", "switching view does not discard unsaved edits in either side".
- [x] 5.2 [AC-6][AC-7] Implement `packages/web/src/components/playbook-pane.tsx` with the dual-view toggle, the seven local-state fields, and `useQuery` initial population; 5.1 turns green.
- [x] 5.3 [AC-8] Action for "PlaybookPane React component with view-mode toggle" (RED, save flow): in `playbook-pane.test.tsx` add a case where typing values, clicking save, then resolving the mutation issues exactly one PUT carrying all seven fields and updates the visible content.
- [x] 5.4 [AC-8] Wire the save button in `playbook-pane.tsx` to `useUpsertPlaybookMutation`; 5.3 turns green.

## 6. Embed PlaybookPane into meeting detail page (covers "Embed PlaybookPane into the meeting detail page")

- [x] 6.1 [AC-6] Action for "Embed PlaybookPane into the meeting detail page" (RED): in `packages/web/src/routes/meetings/detail.test.tsx` add a case asserting `<PlaybookPane meetingId={id}>` is rendered when the meeting query resolves successfully.
- [x] 6.2 [AC-6] Edit `packages/web/src/routes/meetings/detail.tsx` so the rendered detail card is followed by `<PlaybookPane meetingId={meetingId} />`; 6.1 turns green.

## 7. i18n keys and documentation

- [x] 7.1 [AC-9] [P] Covers Requirement: "All UI strings live in both locale files". Add the `playbook.*` namespace to BOTH `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` covering: view-toggle labels (`playbook.toggle.freeform`, `playbook.toggle.structured`), the six structured field labels, save button states (`playbook.save.idle`, `playbook.save.saving`, `playbook.save.saved`), error fallback (`playbook.errors.fallback`); update `packages/web/src/locales/locales.test.ts` with explicit assertions for the new required keys so adding a key to only one locale fails CI.
- [x] 7.2 Update `docs/agents/meetings.md` with a short "Playbook" subsection describing the dual-view editor, the `PlaybookRepository` invariant (single access path), and the auto-create-on-first-read GET semantics.
- [x] 7.3 Verify all acceptance criteria from the agent brief are checked off in GitHub Issue #6.
