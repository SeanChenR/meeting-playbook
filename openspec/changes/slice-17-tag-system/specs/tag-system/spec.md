## ADDED Requirements

### Requirement: tag table stores per-user tag definitions with case-insensitive uniqueness

The backend SHALL provide a `tag` table with columns `(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, color TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())`. The `user_id` column SHALL reference Better Auth `user.id` with `ON DELETE CASCADE` so a deleted user's tags are removed. A unique expression index `(user_id, lower(name))` SHALL prevent the same user from creating two tags whose names differ only by case or surrounding whitespace. The `color` column SHALL be one of the values in the project's preset palette (`packages/backend/meeting_playbook/tags/colors.py`); arbitrary hex strings outside the palette SHALL be rejected at write time. The `name` column SHALL be trimmed of leading and trailing whitespace before persistence.

#### Scenario: Same user cannot create two tags whose names differ only by case

- **GIVEN** user `u_a` has an existing tag `{name: "客戶X"}`
- **WHEN** the user creates a new tag with `name: "客戶x"` (lowercase x)
- **THEN** the create SHALL fail with HTTP 422 and `error_code = "tag.name_taken"`, and the `tag` table SHALL still contain exactly one row matching `(user_id = "u_a", lower(name) = "客戶x")`

#### Scenario: Different users can use the same tag name independently

- **GIVEN** user `u_a` has a tag named `客戶X`
- **WHEN** user `u_b` creates a tag with `name: "客戶X"`
- **THEN** the create SHALL succeed and the `tag` table SHALL contain two rows, one per user

#### Scenario: Color outside palette is rejected

- **GIVEN** an authenticated user and the preset palette `["#A3E635", "#F472B6", ...]` defined in colors.py
- **WHEN** the user creates a tag with `color: "#123456"` (not in palette)
- **THEN** the response SHALL be HTTP 422 with `error_code = "tag.invalid_color"`, and no row SHALL be written

#### Scenario: Whitespace around name is trimmed before uniqueness check

- **GIVEN** user `u_a` creates a tag with `name: "  客戶X  "` (with surrounding spaces)
- **WHEN** the create succeeds and the user then attempts to create `"客戶X"` (no spaces)
- **THEN** the persisted name SHALL be `客戶X` (trimmed), and the second create attempt SHALL fail with `error_code = "tag.name_taken"`

#### Scenario: Deleting the user cascades to tag rows

- **GIVEN** user `u_a` owns three tag rows
- **WHEN** the corresponding `user` row is deleted by Better Auth
- **THEN** all three `tag` rows for `u_a` SHALL be removed by the database CASCADE without manual cleanup

### Requirement: meeting_tag junction table associates meetings with tags

The backend SHALL provide a `meeting_tag` table with columns `(meeting_id TEXT NOT NULL, tag_id TEXT NOT NULL, attached_at TIMESTAMPTZ NOT NULL DEFAULT now())` and composite primary key `(meeting_id, tag_id)`. Both foreign keys SHALL be declared `ON DELETE CASCADE` so deleting a meeting OR a tag automatically removes the matching junction rows. Attaching the same `(meeting_id, tag_id)` pair twice SHALL be idempotent — the repository SHALL return the existing row without raising.

#### Scenario: Deleting a tag cascades to junction rows

- **GIVEN** tag `t_a` is attached to three meetings via `meeting_tag`
- **WHEN** the row for `t_a` in `tag` is deleted via `TagRepository.delete(user_id, "t_a")`
- **THEN** all three `meeting_tag` rows referencing `t_a` SHALL be removed by the database CASCADE, AND no `meeting_tag` row referencing `t_a` SHALL remain

#### Scenario: Deleting a meeting cascades to junction rows

- **GIVEN** meeting `m_x` has two tags attached via `meeting_tag`
- **WHEN** the row for `m_x` in `meeting` is deleted
- **THEN** both `meeting_tag` rows referencing `m_x` SHALL be removed by the database CASCADE; the underlying `tag` rows SHALL remain untouched

#### Scenario: Re-attaching the same tag to the same meeting is idempotent

- **GIVEN** meeting `m_x` already has tag `t_a` attached
- **WHEN** the client POSTs `{tag_id: "t_a"}` to `/api/meetings/m_x/tags` a second time
- **THEN** the response SHALL be HTTP 201 with the existing `attached_at`, and there SHALL still be exactly one `meeting_tag` row for `(m_x, t_a)`

### Requirement: TagRepository enforces case-insensitive uniqueness, cascade-on-delete, and per-meeting limit

The backend SHALL provide `TagRepository` at `packages/backend/meeting_playbook/tags/repository.py` with methods `list_for_user`, `create`, `update`, `delete`, `attach`, and `detach`. The repository SHALL trim whitespace from incoming `name` values before persistence. `create` and `update` SHALL raise `TagNameTaken` (mapped to HTTP 422 `tag.name_taken`) when the resulting `(user_id, lower(name))` conflicts with an existing row, and `InvalidTagColor` (mapped to HTTP 422 `tag.invalid_color`) when the color is not in the preset palette. `delete(user_id, tag_id)` SHALL issue a single `DELETE FROM tag WHERE id = :tag_id AND user_id = :user_id` and rely on the database `ON DELETE CASCADE` foreign key to remove the junction rows. `attach(user_id, meeting_id, tag_id)` SHALL execute inside a transaction, lock the existing junction rows for the meeting via `SELECT ... FOR UPDATE`, and raise `TagLimitExceeded(current_count)` (mapped to HTTP 422 `tag.too_many_for_meeting`) when the meeting already has 10 tags. Attaching the same `(meeting_id, tag_id)` pair twice SHALL return the existing row idempotently rather than raising.

#### Scenario: create rejects duplicate name that differs only by case

- **GIVEN** user `u_a` has a tag named `客戶X`
- **WHEN** `TagRepository.create(user_id="u_a", name="客戶x", color="#A3E635")` runs
- **THEN** the call SHALL raise `TagNameTaken`, and the `tag` row count for `u_a` with `lower(name) = "客戶x"` SHALL remain exactly 1

#### Scenario: delete cascades junction rows via FK

- **GIVEN** user `u_a` has tag `t_a` attached to three meetings
- **WHEN** `TagRepository.delete(user_id="u_a", tag_id="t_a")` runs
- **THEN** the `tag` row for `t_a` SHALL be removed, AND all three `meeting_tag` rows referencing `t_a` SHALL be removed without an explicit junction DELETE statement in the repository call

#### Scenario: attach rejects when the meeting already has 10 tags

- **GIVEN** meeting `m_x` already has 10 distinct tags attached
- **WHEN** `TagRepository.attach(user_id="u_a", meeting_id="m_x", tag_id="t_11")` runs with an eleventh tag
- **THEN** the call SHALL raise `TagLimitExceeded` whose `current_count` attribute equals 10, AND the `meeting_tag` row count for `m_x` SHALL remain exactly 10

#### Scenario: attach is idempotent for duplicate pairs

- **GIVEN** meeting `m_x` already has tag `t_a` attached with `attached_at = T0`
- **WHEN** `TagRepository.attach(user_id="u_a", meeting_id="m_x", tag_id="t_a")` runs a second time
- **THEN** the call SHALL return the existing row with `attached_at = T0`, AND no second `meeting_tag` row SHALL be inserted

#### Scenario: detach of non-existent pair is a no-op

- **GIVEN** meeting `m_x` does NOT have tag `t_b` attached
- **WHEN** `TagRepository.detach(user_id="u_a", meeting_id="m_x", tag_id="t_b")` runs
- **THEN** the call SHALL return without raising, AND the row count in `meeting_tag` for `m_x` SHALL remain unchanged

### Requirement: GET /api/tags lists per-user tags with optional meeting_count

The backend SHALL expose `GET /api/tags` returning the authenticated user's tags as a JSON array. When the query parameter `with_meeting_count=true` is supplied, each item SHALL include a `meeting_count: integer` field computed as `COUNT(*) FROM meeting_tag WHERE tag_id = :id`; otherwise the `meeting_count` field SHALL be omitted from the response payload. Items SHALL be sorted by `created_at` ascending (oldest first) so the settings management page can show stable ordering across renders.

#### Scenario: List returns only tags owned by the requesting user

- **GIVEN** user `u_a` owns tags `[t_1, t_2]` and user `u_b` owns tag `t_3`
- **WHEN** user `u_a` sends `GET /api/tags`
- **THEN** the response body SHALL be `[{id: t_1, ...}, {id: t_2, ...}]` and SHALL NOT contain `t_3`

#### Scenario: with_meeting_count=true adds meeting_count field

- **GIVEN** user `u_a` has tag `t_1` attached to 5 meetings and tag `t_2` attached to 0 meetings
- **WHEN** user `u_a` sends `GET /api/tags?with_meeting_count=true`
- **THEN** the response SHALL include `{id: t_1, ..., meeting_count: 5}` and `{id: t_2, ..., meeting_count: 0}`

#### Scenario: with_meeting_count omitted means no meeting_count field

- **GIVEN** user `u_a` has tag `t_1` attached to 3 meetings
- **WHEN** user `u_a` sends `GET /api/tags` (without the query param)
- **THEN** the response item for `t_1` SHALL NOT contain a `meeting_count` key

### Requirement: POST / PATCH / DELETE /api/tags manage a single tag with strict ownership and validation

The backend SHALL expose:

- `POST /api/tags` with body `{name: string, color: string}` → HTTP 201 `{id, name, color, created_at}` on success
- `PATCH /api/tags/{tag_id}` with body `{name?: string, color?: string}` → HTTP 200 with the updated tag
- `DELETE /api/tags/{tag_id}` → HTTP 204

All three endpoints SHALL scope by `X-User-Id`; operating on a tag owned by another user SHALL return HTTP 404 with no body distinguishing "not found" from "not yours". Failed validation SHALL return HTTP 422 with one of the error codes `tag.name_taken`, `tag.invalid_color`, or `tag.name_required` (empty / whitespace-only name). The `DELETE` endpoint SHALL succeed and cascade junction rows even when the tag is currently attached to meetings.

#### Scenario: PATCH another user's tag returns 404

- **GIVEN** tag `t_3` is owned by user `u_b`
- **WHEN** user `u_a` sends `PATCH /api/tags/t_3` with `{name: "stolen"}`
- **THEN** the response SHALL be HTTP 404, the response body MUST NOT confirm that `t_3` exists, AND the row for `t_3` SHALL remain unchanged in the database

#### Scenario: DELETE removes the tag and cascades junction rows

- **GIVEN** user `u_a` owns tag `t_1` currently attached to 4 meetings
- **WHEN** user `u_a` sends `DELETE /api/tags/t_1`
- **THEN** the response SHALL be HTTP 204, the row for `t_1` SHALL be removed from `tag`, AND all 4 `meeting_tag` rows for `t_1` SHALL be removed

#### Scenario: POST with empty name is rejected

- **WHEN** user `u_a` sends `POST /api/tags` with body `{name: "   ", color: "#A3E635"}`
- **THEN** the response SHALL be HTTP 422 with `error_code = "tag.name_required"`, AND no row SHALL be written

### Requirement: POST / DELETE /api/meetings/{id}/tags attach and detach tags with per-meeting limit

The backend SHALL expose:

- `POST /api/meetings/{meeting_id}/tags` with body `{tag_id: string}` → HTTP 201 `{meeting_id, tag_id, attached_at}` on success
- `DELETE /api/meetings/{meeting_id}/tags/{tag_id}` → HTTP 204

Both endpoints SHALL scope by `X-User-Id`. When the meeting is not owned by the user, OR the tag is not owned by the user, the response SHALL be HTTP 404. When attaching would push the meeting beyond 10 tags, the response SHALL be HTTP 422 with `error_code = "tag.too_many_for_meeting"` and a message containing the current count. The `DELETE` endpoint SHALL be idempotent — removing a tag that is not attached SHALL still return HTTP 204.

#### Scenario: Attach an 11th tag is rejected

- **GIVEN** meeting `m_x` (owned by `u_a`) already has 10 tags attached
- **WHEN** user `u_a` sends `POST /api/meetings/m_x/tags` with body `{tag_id: "t_11"}`
- **THEN** the response SHALL be HTTP 422 with `error_code = "tag.too_many_for_meeting"`, the message SHALL contain "10" (the current count), AND the row count in `meeting_tag` for `m_x` SHALL remain 10

#### Scenario: Detach a non-attached tag returns 204 (idempotent)

- **GIVEN** meeting `m_x` (owned by `u_a`) is NOT currently tagged with `t_b`
- **WHEN** user `u_a` sends `DELETE /api/meetings/m_x/tags/t_b`
- **THEN** the response SHALL be HTTP 204, AND the row count in `meeting_tag` for `m_x` SHALL remain unchanged

#### Scenario: Attach using another user's tag returns 404

- **GIVEN** tag `t_b` is owned by user `u_b`, meeting `m_x` is owned by `u_a`
- **WHEN** user `u_a` sends `POST /api/meetings/m_x/tags` with body `{tag_id: "t_b"}`
- **THEN** the response SHALL be HTTP 404, AND no row SHALL be inserted into `meeting_tag`

### Requirement: TagChip, TagPicker, and TagFilter components render tags in all meeting views

The frontend SHALL ship three components under `packages/web/src/components/tags/`:

- `<TagChip>` — display-only chip rendering `{name, color}` with computed readable text color (dark text on light backgrounds, light text on dark backgrounds). Used in meeting list rows, kanban cards, calendar event pills, meeting detail header, and inside `<TagFilter>` selected items.
- `<TagPicker>` — popover trigger ("+ 新增標籤" / "+ Add tag") that opens a `Command`-based search input. Existing tags appear as a clickable list; when the search string does not match any existing tag, a "Create '{query}'" inline-create row SHALL appear. Already-attached tags SHALL display a check mark; clicking them SHALL detach. Inline create SHALL chain `POST /api/tags` followed by `POST /api/meetings/{id}/tags`.
- `<TagFilter>` — multi-select dropdown that lists all of the user's tags with checkboxes. Selected state SHALL be reflected in the URL search parameter `tag_ids` as a comma-separated list. The dropdown trigger SHALL show "標籤 (N)" / "Tags (N)" where N is the selected count.

All visible strings in these components SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`.

#### Scenario: TagChip computes readable text color from background

- **GIVEN** the preset palette contains a light color `#FEF3C7` and a dark color `#7C2D12`
- **WHEN** `<TagChip name="X" color="#FEF3C7" />` and `<TagChip name="Y" color="#7C2D12" />` are rendered
- **THEN** the first chip SHALL apply the dark-text variant CSS class and the second chip SHALL apply the light-text variant; both SHALL pass an automated contrast check (WCAG AA, 4.5:1 minimum)

#### Scenario: TagPicker inline-create chains tag create and attach

- **GIVEN** the user opens `<TagPicker meetingId="m_x" currentTags={[]} />` and types "客戶Y" which does not match any existing tag
- **WHEN** the user clicks the "Create '客戶Y'" inline row
- **THEN** the component SHALL issue `POST /api/tags` with `{name: "客戶Y", color: <default-palette[0]>}`, then on HTTP 201 SHALL issue `POST /api/meetings/m_x/tags` with the new `tag_id`, AND on HTTP 201 SHALL call `onAttached(newTag)` to update the parent

#### Scenario: TagFilter writes selection to URL search param

- **GIVEN** the user is on `/meetings?view=list` with no tag filter
- **WHEN** the user opens `<TagFilter>` and checks tags `t_a` and `t_b`
- **THEN** the URL SHALL update to `/meetings?view=list&tag_ids=t_a,t_b`, AND a page reload SHALL preserve the filter selection

#### Scenario: TagFilter shows selected count in trigger label

- **GIVEN** the user has selected 2 tags in `<TagFilter>`
- **WHEN** the dropdown is closed
- **THEN** the trigger button SHALL display "標籤 (2)" in zh-TW or "Tags (2)" in en

### Requirement: /settings/tags page provides CRUD with dynamic delete confirmation

The frontend SHALL ship a route `/settings/tags` that renders the user's tags as a list. Each row SHALL allow inline rename, recolor (swatch picker showing the preset palette), and hard delete. The hard-delete action SHALL open an `AlertDialog` whose description text dynamically displays the number of meetings the tag is currently attached to, sourced from the `meeting_count` field returned by `GET /api/tags?with_meeting_count=true`. The description text SHALL use ICU plural formatting in the en locale (`"This tag is attached to {count, plural, one {1 meeting} other {# meetings}}"`); the zh-TW locale SHALL use the single form "此標籤目前掛在 {count} 個會議上". Successful delete SHALL remove the row from the list without a page reload.

#### Scenario: Delete confirmation shows the current attach count

- **GIVEN** the user is on `/settings/tags` and tag `t_a` has `meeting_count: 5` from the list response
- **WHEN** the user clicks the delete icon on the `t_a` row
- **THEN** the AlertDialog description SHALL render "此標籤目前掛在 5 個會議上，刪除後將從這些會議移除。" (zh-TW) or "This tag is attached to 5 meetings; deleting will remove it from each. This cannot be undone." (en)

#### Scenario: Inline rename validates duplicate name with backend error code

- **GIVEN** user `u_a` has tags `[客戶X, 客戶Y]` and renames `客戶Y` to `客戶x`
- **WHEN** the inline-rename PATCH returns HTTP 422 with `error_code = "tag.name_taken"`
- **THEN** the row SHALL surface the localized error message via `localizedErrorMessage("tag.name_taken", t)`, the row SHALL revert to displaying `客戶Y`, AND the rename input SHALL remain focused so the user can correct it

#### Scenario: Recolor swatch only shows preset palette

- **WHEN** the user opens the color swatch for any tag row
- **THEN** the swatch picker SHALL render exactly the palette colors defined in `packages/web/src/lib/tag-palette.ts`, AND there SHALL NOT be any free-form hex input field

##### Example: zh-TW plural form is the same regardless of count

| count | en rendered                                                              | zh-TW rendered                                |
| ----- | ------------------------------------------------------------------------ | --------------------------------------------- |
| 0     | This tag is attached to 0 meetings; deleting will remove it from each.   | 此標籤目前掛在 0 個會議上，刪除後將從這些會議移除。 |
| 1     | This tag is attached to 1 meeting; deleting will remove it from each.    | 此標籤目前掛在 1 個會議上，刪除後將從這些會議移除。 |
| 5     | This tag is attached to 5 meetings; deleting will remove it from each.   | 此標籤目前掛在 5 個會議上，刪除後將從這些會議移除。 |
