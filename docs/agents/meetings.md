# Meetings — agent notes

> Slice 3 (`slice-03-meeting-crud`) outcome.
> Spec: `openspec/specs/meeting-management/spec.md` (after archive).
> ADRs in scope: ADR-0012 (PostgreSQL + Alembic), ADR-0021 (gateway-trusting backend), ADR-0025 (no TS ORM), ADR-0016 (binary speaker labels with two display names).

## End-to-end flow

```
Browser
  ├─ /meetings           list page
  ├─ /meetings/new       create form
  └─ /meetings/:id       detail + delete
       │
       ▼
Bun.serve gateway        validates Better Auth session, injects X-User-Id
       │
       ▼
FastAPI                  trusts X-User-Id, no re-validation
  /api/meetings (POST/GET list/GET id/DELETE)
       │
       ▼
MeetingRepository        async SQLAlchemy 2.0 — the SOLE access path
       │
       ▼
PostgreSQL `meeting`     FK → user.id ON DELETE CASCADE
```

## The MeetingRepository invariant

`packages/backend/meeting_playbook/meetings/repository.py` is the **single
access path** for the `meeting` table. Every higher layer (router, future
slices for transcripts, playbooks, recordings) MUST go through this
repository. Direct ORM queries that bypass it are a review block — they
break ownership scoping.

The repository's contract:

| Method | Signature | Returns |
| --- | --- | --- |
| `create` | `user_id, title, counterparty_display_name, me_display_name, asr_provider="whisper"` | `Meeting` |
| `list_by_user` | `user_id` | `list[Meeting]` (DESC `created_at`) |
| `get_for_user` | `user_id, meeting_id` | `Meeting | None` (collapses missing + owner-mismatch) |
| `delete_for_user` | `user_id, meeting_id` | `bool` (false = missing or other-owner) |

## Ownership isolation

Per spec `Requirement: Meeting belongs to exactly one user with strict
ownership isolation`: cross-user reads and deletes return HTTP 404 with no
existence leak in the body. The repository surface enforces this by
returning `None` / `False` uniformly; the router maps both to 404 with
`error_code: meeting.not_found`.

## Default values

- `status` → `"scheduled"`. Client-supplied `status` is ignored on POST
  (status transitions belong to a later slice).
- `asr_provider` → `"whisper"`. Logical name; the ASR provider registry
  maps it to a concrete implementation.
- `calendar_event_id` → `null`. A later slice will populate this when
  Google Calendar integration lands.

## Scope of this slice

In scope:
- `meeting` table schema + Alembic migration
- `MeetingRepository` + `MeetingRead` / `MeetingCreate` schemas
- `POST /api/meetings`, `GET /api/meetings`, `GET /api/meetings/{id}`,
  `DELETE /api/meetings/{id}`
- Three React routes: `/meetings`, `/meetings/new`, `/meetings/:id`
- `meetings-api.ts` + `MeetingApiError` for typed error envelope
- i18n keys mirrored across `zh-TW.json` and `en.json`

Out of scope (deferred to later slices):
- `PATCH /api/meetings/{id}` (no edit; delete + recreate)
- Status transitions (Slice 6)
- Calendar event linking (Slice 5)
- Pagination / search / batch ops
- Any child entities other than the playbook (transcript, audio, advisor)

## Playbook (Slice 4)

`playbook` is a child entity FK'd to `meeting.id` ON DELETE CASCADE with a
`UNIQUE(meeting_id)` constraint — exactly one playbook per meeting.

Two endpoints, both gated by meeting ownership through
`MeetingRepository.get_for_user`:

- `GET /api/meetings/{id}/playbook` — auto-creates an empty row on first
  read so the editor always has an editable surface; subsequent reads
  return the same `id`. Cross-user reads return 404 + `meeting.not_found`
  (no existence leak).
- `PUT /api/meetings/{id}/playbook` — full upsert of the seven content
  fields (`free_form_markdown`, `objective`, `counterparty_profile`,
  `anticipated_topics`, `anticipated_objections`, `talking_points`,
  `red_lines`). Missing fields default to the empty string. `updated_at`
  advances on every write.

`PlaybookRepository` is the **single access path** for the table; future
slices (LLM generation in Slice 5, advisor in Slice 6, in-meeting display
in Slice 8) MUST go through this repo and MUST NOT issue raw SQL against
the `playbook` table.

The frontend `PlaybookPane` component is mounted on the meeting detail
page. It renders a view-mode toggle (free-form ↔ structured), preserves
unsaved edits in both views during a toggle, and dispatches one PUT
covering all seven fields when the save button is clicked. The
`useUpsertPlaybookMutation(meetingId)` hook invalidates the
`["playbook", meetingId]` cache on success.
