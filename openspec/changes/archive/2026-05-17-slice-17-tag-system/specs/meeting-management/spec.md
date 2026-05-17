## MODIFIED Requirements

### Requirement: Meeting list is sorted newest-first by creation time

The `GET /api/meetings` endpoint SHALL return meetings owned by the authenticated user in descending order of `created_at`. When the user owns no meetings, the response SHALL be HTTP 200 with an empty array body, never HTTP 404. Each item in the response SHALL include a `tags: [{id, name, color}]` array populated via a single batched query (the `MeetingRepository.list_for_user(...)` SHALL use `selectinload(Meeting.tags)` so listing N meetings does NOT issue N+1 queries against `tag` / `meeting_tag`). The endpoint SHALL accept an optional `tag_ids` query parameter formatted as a comma-separated list of tag ids; when supplied, the response SHALL include ONLY meetings that have ALL listed tags attached (AND semantics), preserving the descending-`created_at` sort within the filtered subset. When `tag_ids` is empty (param omitted or set to ""), the filter SHALL be a no-op. When any value inside `tag_ids` is not a tag owned by the authenticated user, the response SHALL be HTTP 422 with `error_code = "tag.unknown_id"`; the response MUST NOT silently drop the unknown id and return partial results.

#### Scenario: Multiple meetings sort newest first

- **GIVEN** user A owns three meetings with `created_at` timestamps T1 < T2 < T3
- **WHEN** user A sends `GET /api/meetings`
- **THEN** the response body SHALL be a list ordered T3, T2, T1

#### Scenario: Empty list returns 200 with empty array

- **GIVEN** user A owns zero meetings
- **WHEN** user A sends `GET /api/meetings`
- **THEN** the response status SHALL be HTTP 200 and the body SHALL be an empty JSON array

#### Scenario: Each meeting item includes a tags array

- **GIVEN** user A owns meeting `m_1` with tags `[{id: t_a, name: 客戶X, color: #A3E635}]` attached, and meeting `m_2` with no tags
- **WHEN** user A sends `GET /api/meetings`
- **THEN** the response item for `m_1` SHALL contain `tags: [{id: "t_a", name: "客戶X", color: "#A3E635"}]`, AND the response item for `m_2` SHALL contain `tags: []`

#### Scenario: tag_ids query filters with AND semantics

- **GIVEN** user A owns three meetings: `m_1` tagged `[t_a, t_b]`, `m_2` tagged `[t_a]`, `m_3` tagged `[t_b, t_c]`
- **WHEN** user A sends `GET /api/meetings?tag_ids=t_a,t_b`
- **THEN** the response SHALL contain only `m_1` (the only meeting with BOTH `t_a` AND `t_b`), AND SHALL NOT contain `m_2` or `m_3`

#### Scenario: tag_ids referencing another user's tag returns 422

- **GIVEN** tag `t_x` is owned by user B (not user A)
- **WHEN** user A sends `GET /api/meetings?tag_ids=t_x`
- **THEN** the response SHALL be HTTP 422 with `error_code = "tag.unknown_id"`, AND the response body MUST NOT include any meeting payload

#### Scenario: Empty tag_ids parameter is a no-op

- **GIVEN** user A owns three meetings (none required to be tagged)
- **WHEN** user A sends `GET /api/meetings?tag_ids=`
- **THEN** the response SHALL be identical to `GET /api/meetings` (all owned meetings returned, descending-`created_at`)

#### Scenario: Listing many meetings does not trigger N+1 tag queries

- **GIVEN** user A owns 50 meetings, each with 0–10 tags attached
- **WHEN** user A sends `GET /api/meetings` and the SQL query log is observed
- **THEN** the count of SQL `SELECT` statements issued against `tag` and `meeting_tag` combined SHALL be at most 2 (one for the meetings query, one for the batched selectinload), NOT 50 or more

### Requirement: GET /api/meetings/{id} returns recordings_available and rerun_asr_pending derived fields

The `GET /api/meetings/{meeting_id}` endpoint SHALL return the meeting record with two derived boolean fields computed from the related `recording` rows:

- `recordings_available: bool` — `true` when at least one `recording` row exists for the meeting whose `wav_path` file is still on disk AND whose `expired_at` is NULL or in the future. `false` otherwise (no recordings, all expired by retention, or files missing from disk).
- `rerun_asr_pending: bool` — `true` when `recordings_available` is true AND the meeting has at least one `transcript_chunk` already (i.e., re-ASR is a meaningful operation, not a first ASR run). `false` otherwise.

In addition to these derived fields and the existing meeting columns, the response SHALL include `tags: [{id, name, color}]` containing every tag currently attached to the meeting. The response SHALL be HTTP 200 with these fields populated for a meeting owned by the user, OR HTTP 404 when the meeting does not exist or is owned by another user.

#### Scenario: Recordings exist and at least one file still on disk

- **GIVEN** meeting `m_a` has two `recording` rows, both with `wav_path` files present on disk and `expired_at` NULL
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `recordings_available: true`

#### Scenario: Recordings exist but files cleaned up by retention

- **GIVEN** meeting `m_a` has two `recording` rows whose `expired_at` is in the past AND whose `wav_path` files are absent from disk
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `recordings_available: false`

#### Scenario: No recordings at all

- **GIVEN** meeting `m_a` has zero `recording` rows
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `recordings_available: false` and `rerun_asr_pending: false`

#### Scenario: Recordings available and transcript exists makes rerun pending true

- **GIVEN** meeting `m_a` has recordings available AND at least one `transcript_chunk` row exists for `m_a`
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `rerun_asr_pending: true`

#### Scenario: Recordings available but no transcript yet

- **GIVEN** meeting `m_a` has recordings available AND zero `transcript_chunk` rows
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `rerun_asr_pending: false`

#### Scenario: Detail payload includes attached tags

- **GIVEN** meeting `m_a` (owned by user A) has tags `[{id: t_a, name: 客戶X, color: #A3E635}, {id: t_b, name: 面試, color: #F472B6}]` attached
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `tags: [{id: "t_a", name: "客戶X", color: "#A3E635"}, {id: "t_b", name: "面試", color: "#F472B6"}]` and the order SHALL follow `attached_at` ascending

#### Scenario: Detail payload contains empty tags array when no tags attached

- **GIVEN** meeting `m_a` (owned by user A) has zero tags attached
- **WHEN** user A sends `GET /api/meetings/m_a`
- **THEN** the response body SHALL contain `tags: []`
