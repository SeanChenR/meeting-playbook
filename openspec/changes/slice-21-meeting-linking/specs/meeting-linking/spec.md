## ADDED Requirements

### Requirement: `meeting_link` table stores one row per bidirectional related-meetings pair

The system SHALL persist meeting links in a `meeting_link` table whose columns
are `(id UUID PK, from_meeting_id UUID NOT NULL, to_meeting_id UUID NOT NULL,
link_type TEXT NOT NULL DEFAULT 'related', created_at TIMESTAMPTZ NOT NULL
DEFAULT now())`. Both `from_meeting_id` and `to_meeting_id` SHALL reference
`meeting(id)` with `ON DELETE CASCADE`. The table SHALL enforce
`from_meeting_id <> to_meeting_id` via a CHECK constraint, SHALL enforce
`link_type IN ('related')` for v1.1 via a CHECK constraint, and SHALL enforce
order-independent pair uniqueness via a unique index on
`(LEAST(from_meeting_id, to_meeting_id), GREATEST(from_meeting_id, to_meeting_id))`.

#### Scenario: Forward and reverse insert collapse to the same uniqueness key

- **GIVEN** an empty `meeting_link` table and two existing meetings A and B
- **WHEN** the system inserts a row with `from_meeting_id = A, to_meeting_id = B`
- **AND** then attempts to insert a second row with
  `from_meeting_id = B, to_meeting_id = A`
- **THEN** the second insert SHALL fail with a unique constraint violation on
  the `(LEAST, GREATEST)` index

#### Scenario: Self-reference rejected by CHECK constraint

- **GIVEN** an existing meeting A
- **WHEN** the system attempts to insert a row with
  `from_meeting_id = A, to_meeting_id = A`
- **THEN** the insert SHALL fail with a CHECK constraint violation

#### Scenario: Deleting a meeting cascades to its links

- **GIVEN** meetings A and B with one `meeting_link` row between them
- **WHEN** meeting A is deleted from the `meeting` table
- **THEN** the corresponding `meeting_link` row SHALL be removed by FK cascade
- **AND** `SELECT count(*) FROM meeting_link WHERE from_meeting_id = A OR to_meeting_id = A`
  SHALL return zero

---

### Requirement: `MeetingLinkRepository` exposes bidirectional list / create / delete operations

The `MeetingLinkRepository` SHALL expose four methods that hide row direction
from callers:

- `list_for_meeting(meeting_id) -> list[MeetingLinkView]` MUST return every
  link whose `from_meeting_id` OR `to_meeting_id` equals `meeting_id`,
  projected so that each view's `other_meeting_id` is always the meeting on
  the opposite side of `meeting_id`.
- `create(from_meeting_id, to_meeting_id, link_type="related") -> MeetingLink`
  MUST insert a single row, MUST raise `MeetingLinkSelfReference` when
  `from_meeting_id == to_meeting_id`, and MUST raise `MeetingLinkDuplicate`
  when the pair (in either order) already exists.
- `delete(link_id) -> bool` MUST delete the row identified by `link_id` and
  return `True` when one row was deleted, `False` when zero rows matched.
- `get(link_id) -> MeetingLink | None` MUST return the row identified by
  `link_id` or `None`.

The repository MUST NOT expose row direction (from/to) in any return value
intended for application or UI consumption; that detail is internal.

#### Scenario: Write one row, both sides query it back

- **GIVEN** meetings A and B owned by the same user and no existing links
- **WHEN** the system calls `create(from_meeting_id=A, to_meeting_id=B)`
- **AND** then calls `list_for_meeting(A)` and separately `list_for_meeting(B)`
- **THEN** both calls SHALL return a list of length 1
- **AND** `list_for_meeting(A)[0].other_meeting_id` SHALL equal B
- **AND** `list_for_meeting(B)[0].other_meeting_id` SHALL equal A
- **AND** both views SHALL share the same `link_id` and `created_at`

#### Scenario: Reverse-order create raises MeetingLinkDuplicate

- **GIVEN** an existing link created with `(from=A, to=B)`
- **WHEN** the system calls `create(from_meeting_id=B, to_meeting_id=A)`
- **THEN** the call SHALL raise `MeetingLinkDuplicate`
- **AND** the `meeting_link` table SHALL still contain exactly one row for
  the pair {A, B}

#### Scenario: Self-reference raises MeetingLinkSelfReference

- **GIVEN** an existing meeting A
- **WHEN** the system calls `create(from_meeting_id=A, to_meeting_id=A)`
- **THEN** the call SHALL raise `MeetingLinkSelfReference`
- **AND** no row SHALL be written to `meeting_link`

#### Scenario: Delete is idempotent at the row level

- **GIVEN** a link with id `L` between meetings A and B
- **WHEN** the system calls `delete(L)` once and then `delete(L)` a second time
- **THEN** the first call SHALL return `True` and remove the row
- **AND** the second call SHALL return `False` and SHALL NOT raise

---

### Requirement: `GET /api/meetings/{id}/links` returns bidirectional related links for the meeting

The system SHALL expose `GET /api/meetings/{id}/links` that returns every link
where `meeting_id == id` appears on either end. The response body SHALL be
`{"links": [MeetingLinkView, ...]}` where each `MeetingLinkView` includes
`link_id`, `other_meeting_id`, `other_meeting_title`,
`other_meeting_scheduled_start_at`, `link_type`, and `created_at`. The list
SHALL be sorted by `created_at` descending. The endpoint SHALL respond with
HTTP 404 and `error_code = "meeting.not_found"` when the meeting at `id` does
not exist or does not belong to the current user identified by the
`X-User-Id` header.

#### Scenario: User views related links for their own meeting

- **GIVEN** the current user owns meetings A and B and a link exists between them
- **WHEN** the client calls `GET /api/meetings/A/links`
- **THEN** the response SHALL be HTTP 200
- **AND** the response body SHALL contain exactly one link whose
  `other_meeting_id` equals B and whose `other_meeting_title` equals the
  meeting B title

#### Scenario: Ownership isolation hides another user's meeting

- **GIVEN** meeting A belongs to user U1 and the current user is U2
- **WHEN** U2 calls `GET /api/meetings/A/links`
- **THEN** the response SHALL be HTTP 404 with `error_code = "meeting.not_found"`
- **AND** the response body SHALL NOT reveal that meeting A exists

---

### Requirement: `POST /api/meetings/{id}/links` creates a bidirectional link with duplicate and self-reference guards

The system SHALL expose `POST /api/meetings/{id}/links` accepting a JSON body
`{"to_meeting_id": UUID}`. On success the endpoint SHALL respond with HTTP
201 and `{"link_id": UUID}`. The endpoint SHALL:

- Respond HTTP 404 with `error_code = "meeting.not_found"` when either `id`
  or `to_meeting_id` does not exist or does not belong to the current user.
- Respond HTTP 422 with `error_code = "meeting_link.self_reference"` when
  `to_meeting_id == id`.
- Respond HTTP 409 with `error_code = "meeting_link.duplicate"` when a link
  between `{id, to_meeting_id}` already exists in either direction.

#### Scenario: First-time link creation succeeds

- **GIVEN** the current user owns meetings A and B with no existing link
- **WHEN** the client calls `POST /api/meetings/A/links` with body `{"to_meeting_id": "B"}`
- **THEN** the response SHALL be HTTP 201
- **AND** the response body SHALL contain a `link_id`
- **AND** a subsequent `GET /api/meetings/B/links` SHALL include that link

#### Scenario: Duplicate link rejected regardless of direction

- **GIVEN** a link already exists between meetings A and B created via
  `POST /api/meetings/A/links {"to_meeting_id": "B"}`
- **WHEN** the client calls `POST /api/meetings/B/links` with body `{"to_meeting_id": "A"}`
- **THEN** the response SHALL be HTTP 409 with
  `error_code = "meeting_link.duplicate"`
- **AND** the `meeting_link` table SHALL still contain exactly one row for
  the pair {A, B}

#### Scenario: Self-reference rejected with 422

- **GIVEN** the current user owns meeting A
- **WHEN** the client calls `POST /api/meetings/A/links` with body `{"to_meeting_id": "A"}`
- **THEN** the response SHALL be HTTP 422 with
  `error_code = "meeting_link.self_reference"`
- **AND** no row SHALL be written to `meeting_link`

---

### Requirement: `DELETE /api/meetings/{id}/links/{link_id}` removes the link from either side

The system SHALL expose `DELETE /api/meetings/{id}/links/{link_id}` that
deletes the link identified by `link_id` when at least one end of the link
references a meeting owned by the current user. The endpoint SHALL respond
with HTTP 204 on successful delete and HTTP 404 with
`error_code = "meeting_link.not_found"` when the link does not exist or
neither end belongs to the current user.

#### Scenario: Either-side delete removes the link once

- **GIVEN** a link L between meetings A and B both owned by the current user
- **WHEN** the client calls `DELETE /api/meetings/A/links/L`
- **THEN** the response SHALL be HTTP 204
- **AND** subsequent `GET /api/meetings/A/links` and `GET /api/meetings/B/links`
  SHALL both omit L

#### Scenario: Delete on a foreign link returns 404 without leaking existence

- **GIVEN** a link L exists between meetings owned by user U1 and the current
  user is U2
- **WHEN** U2 calls `DELETE /api/meetings/{any-of-U2-meetings}/links/L`
- **THEN** the response SHALL be HTTP 404 with
  `error_code = "meeting_link.not_found"`
- **AND** the row in `meeting_link` SHALL NOT be deleted

---

### Requirement: `<MeetingLinkPicker>` filters out the current meeting and already-linked meetings from a cached meetings list

The frontend SHALL provide a `<MeetingLinkPicker>` modal that lets the user
search for an existing meeting to link. The picker SHALL read the meetings
list from the React Query cache populated by `meetingsListQueryOptions()` and
SHALL NOT issue a fresh network request to populate it. The picker SHALL
filter out the current meeting and every meeting whose id appears in the
result of `meetingLinksQueryOptions(currentMeetingId)` as `other_meeting_id`.
A case-insensitive substring match against `meeting.title` SHALL filter the
remaining candidates as the user types. When the meetings list cache is
empty (cache miss), the picker SHALL render a `meetings.links.picker.cacheMiss`
hint with a link to the meetings list route instead of an empty result.

#### Scenario: Picker excludes the current meeting and already-linked meetings

- **GIVEN** the React Query cache contains four meetings A, B, C, D belonging
  to the current user
- **AND** meeting A is the current meeting and an existing link already
  associates A with C
- **WHEN** the user opens the picker from meeting A's detail page
- **THEN** the picker candidate list SHALL contain exactly B and D
- **AND** the picker SHALL NOT contain A or C

##### Example: candidate filter table

| Cached meetings | Current meeting | Existing links     | Picker candidates |
| --------------- | --------------- | ------------------ | ----------------- |
| A, B, C, D      | A               | (none)             | B, C, D           |
| A, B, C, D      | A               | A↔C                | B, D              |
| A, B, C, D      | A               | A↔B, A↔C           | D                 |
| A, B, C, D      | A               | A↔B, A↔C, A↔D      | (empty list)      |

#### Scenario: Cache miss surfaces hint instead of empty list

- **GIVEN** the user deep-links into `/meetings/A` without first visiting any
  meetings list route, so the React Query cache is empty
- **WHEN** the user opens the picker
- **THEN** the picker SHALL render the `meetings.links.picker.cacheMiss` hint
- **AND** the hint SHALL include a navigation link to the meetings list route
- **AND** the picker SHALL NOT call `GET /api/meetings` to backfill the cache

---

### Requirement: `meetings.links.*` i18n keys exist in both locales with matching shape

Every user-visible string introduced by this capability SHALL exist in both
`packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json`
under the `meetings.links.*` namespace, and every backend error code emitted
by the meeting-link endpoints SHALL have a matching `errors.meeting_link.*`
key in both locales. The deep-equal locales test SHALL pass.

#### Scenario: Locale parity holds for the new namespace

- **GIVEN** the change has shipped
- **WHEN** `bun --filter @meeting-playbook/web test` runs `locales.test.ts`
- **THEN** the deep-equal comparison between zh-TW.json and en.json structures
  SHALL pass
- **AND** both files SHALL contain the keys `meetings.links.heading`,
  `meetings.links.empty`, `meetings.links.addButton`,
  `meetings.links.picker.placeholder`, `meetings.links.picker.cacheMiss`,
  `errors.meeting_link.duplicate`, `errors.meeting_link.self_reference`,
  and `errors.meeting_link.not_found`
