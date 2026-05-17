## ADDED Requirements

### Requirement: MetadataCard header renders a related-meetings section between prev/next nav and metadata columns

The `/meetings/$id` route SHALL render a `<MeetingLinksSection>` element
inside the MetadataCard header, positioned after the prev/next navigation
group and before the two metadata columns. The section SHALL display:

- A heading using the `meetings.links.heading` i18n key.
- A count derived from `meetings.links.count_one` / `meetings.links.count_other`
  plural keys.
- A list of links each rendered as a navigation link to `/meetings/{other_meeting_id}`
  that displays `other_meeting_title` and `other_meeting_scheduled_start_at`.
- A delete button (trash icon from `animate-ui` or a static lucide icon) on
  each list row that triggers `DELETE /api/meetings/{currentMeetingId}/links/{link_id}`.
- A `+ 關聯` / `+ Link` button (using the `meetings.links.addButton` i18n
  key) that opens the `<MeetingLinkPicker>` modal.

When the meeting has zero links, the section SHALL render the
`meetings.links.empty` empty state and SHALL still render the
`+ 關聯` / `+ Link` button. When the meeting has more than ten links, the
list SHALL render in a collapsed state showing the first ten with a
toggle button that uses the `meetings.links.showMore` /
`meetings.links.showFewer` i18n keys.

The existing prev/next navigation, BackLink, MetadataCard two-column layout,
recording badge, ASR provider selector, and CaptureIndicator behavior SHALL
remain unchanged.

#### Scenario: Empty state renders heading, empty hint, and add button

- **GIVEN** the user navigates to `/meetings/A` and meeting A has zero
  related links
- **WHEN** the MetadataCard header renders
- **THEN** the page SHALL render an element with `data-testid="meeting-links-section"`
- **AND** that element SHALL contain the `meetings.links.heading` text
- **AND** it SHALL contain the `meetings.links.empty` empty-state text
- **AND** it SHALL contain a button with the `meetings.links.addButton` label

#### Scenario: Linked meetings render as navigation links with delete affordance

- **GIVEN** meeting A has two related links to meetings B and C
- **WHEN** the MetadataCard header renders
- **THEN** the meeting-links-section SHALL render a list of two items
- **AND** each item SHALL be an anchor with `href="/meetings/{B-id}"` and
  `href="/meetings/{C-id}"` respectively, showing the other meeting's title
- **AND** each item SHALL render a delete button with
  `data-testid="meeting-link-delete-{link_id}"`

#### Scenario: Collapse triggers when link count exceeds ten

- **GIVEN** meeting A has fifteen related links
- **WHEN** the MetadataCard header renders
- **THEN** the meeting-links-section SHALL render exactly ten link items by
  default
- **AND** a toggle button with the `meetings.links.showMore` label SHALL be
  present
- **AND** clicking the toggle SHALL reveal the remaining five links and
  switch the toggle label to `meetings.links.showFewer`

#### Scenario: Add button opens the MeetingLinkPicker modal

- **GIVEN** the user is on `/meetings/A`
- **WHEN** the user clicks the button labeled `meetings.links.addButton`
- **THEN** a modal element with `data-testid="meeting-link-picker"` SHALL
  open
- **AND** the modal SHALL contain a typeahead input using the
  `meetings.links.picker.placeholder` label

#### Scenario: Successful link creation refreshes the section

- **GIVEN** the user has opened the picker on `/meetings/A` and selected
  meeting B
- **WHEN** the user confirms the selection and the
  `POST /api/meetings/A/links` call returns HTTP 201
- **THEN** the picker modal SHALL close
- **AND** the meeting-links-section SHALL re-render including meeting B in
  the list

#### Scenario: Duplicate link rejection keeps modal open and shows localized error

- **GIVEN** the user has opened the picker on `/meetings/A` and selected
  meeting B
- **AND** meeting A and meeting B are already linked
- **WHEN** the user confirms the selection and the server responds with
  HTTP 409 and `error_code = "meeting_link.duplicate"`
- **THEN** the picker modal SHALL remain open
- **AND** the picker SHALL display the message bound to
  `errors.meeting_link.duplicate` from the active locale

#### Scenario: Delete icon removes the link inline

- **GIVEN** meeting A has a related link to meeting B with link id L
- **WHEN** the user clicks the element with
  `data-testid="meeting-link-delete-L"` and the server responds with HTTP 204
- **THEN** the meeting-links-section SHALL re-render without the row for L
- **AND** the section SHALL fall back to the empty state if L was the only
  link
