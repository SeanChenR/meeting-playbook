## ADDED Requirements

### Requirement: Meeting detail page SHALL render a prev/next navigation group alongside the BackLink

The `/meetings/$id` route SHALL render `[← prev] [BackLink] [next →]`
as a single horizontal group inside the MetadataCard header,
replacing the previous standalone BackLink row.

The prev / next buttons SHALL navigate to the previous / next
meeting in the user's list, sorted by `scheduled_start_at` ASC
NULLS LAST (meetings without a scheduled time sort to the end,
ordered by `created_at` DESC within that tail).

The neighbour lookup SHALL read the React Query cache via
`queryClient.getQueryData(meetingsListQueryOptions().queryKey)`. It
SHALL NOT trigger a fresh fetch.

When the cache is empty (deep-link entry without first visiting
/meetings or /meetings/calendar), both prev and next buttons SHALL
render disabled with a tooltip explaining the gating
("從會議列表進入以啟用前後切換" zh-TW / "Visit the meetings list
first to enable previous / next" en).

When the current meeting is at one end of the sorted list, the
corresponding direction button SHALL render disabled (the other
direction stays active).

#### Scenario: Cache hit, neighbour exists in both directions

- **GIVEN** the user lands on /meetings/list and clicks the second
  meeting card to navigate to /meetings/$id
- **AND** the React Query cache has a list of three meetings
- **WHEN** the MetadataCard header renders
- **THEN** both prev and next buttons SHALL be enabled
- **AND** clicking next SHALL navigate to the third meeting's
  detail page; clicking prev SHALL navigate to the first

#### Scenario: Cache miss

- **GIVEN** the user pastes a /meetings/$id URL directly into the
  browser without visiting /meetings first
- **WHEN** the MetadataCard header renders and the React Query
  list cache is empty
- **THEN** both prev and next buttons SHALL render with a `disabled`
  attribute
- **AND** hovering either button SHALL show a tooltip explaining
  that visiting the meetings list first will enable the navigation
- **AND** the component SHALL NOT issue a network request to
  populate the cache

#### Scenario: Current meeting is the first or last in the sorted list

- **GIVEN** the cache has three meetings sorted by
  `scheduled_start_at` ASC NULLS LAST
- **WHEN** the user views the detail page of the FIRST meeting in
  the sorted order
- **THEN** the prev button SHALL render disabled and the next
  button SHALL render enabled
- **AND** symmetrically, when viewing the LAST meeting the next
  button SHALL render disabled and the prev button SHALL render
  enabled

#### Scenario: Standalone BackLink row removed

- **GIVEN** the codebase after this change ships
- **WHEN** the /meetings/$id route source is scanned
- **THEN** the previous standalone `<BackLink to="/meetings" />` row
  above the MetadataCard SHALL be removed
- **AND** the BackLink SHALL appear ONLY inside the MetadataCard
  header's prev/next nav group
