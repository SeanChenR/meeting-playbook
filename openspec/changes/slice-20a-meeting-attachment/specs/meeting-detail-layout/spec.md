## ADDED Requirements

### Requirement: Meeting detail page renders an Attachments section with the dropzone component

The meeting detail page (`/meetings/{id}`) SHALL render a collapsible "Attachments / 附件" section that hosts the `<AttachmentDropzone>` component. The section SHALL appear below the Playbook pane in BOTH stack mode and columns mode, and SHALL default to expanded on first render. The section's expanded/collapsed state SHALL persist in `localStorage` under the key `meeting-detail.attachments-expanded`. Toggling the section SHALL NOT affect the existing layout switcher state stored under `meeting-detail.layout`.

The section heading SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`. The section SHALL remain mounted across layout switches (stack ↔ columns) so an in-flight upload is not interrupted by the user toggling the layout.

#### Scenario: Section is expanded by default on first visit

- **GIVEN** a user opens `/meetings/m_a` for the first time with no prior `meeting-detail.attachments-expanded` value in `localStorage`
- **WHEN** the page renders
- **THEN** the Attachments section SHALL be visible and expanded, the `<AttachmentDropzone>` SHALL be mounted, and `localStorage["meeting-detail.attachments-expanded"]` SHALL be unset or `"true"`

#### Scenario: Collapse state persists across reloads

- **GIVEN** a user opens `/meetings/m_a` and clicks the section header to collapse it
- **WHEN** the user reloads the page
- **THEN** the Attachments section SHALL render collapsed on reload, `localStorage["meeting-detail.attachments-expanded"]` SHALL equal `"false"`, and the `<AttachmentDropzone>` SHALL still be mounted in the DOM (only visually collapsed)

#### Scenario: Layout switch preserves in-flight upload

- **GIVEN** a user is uploading a 5 MiB PDF and the progress indicator is at 40%
- **WHEN** the user toggles the layout switcher from columns to stack
- **THEN** the `<AttachmentDropzone>` SHALL remain mounted, the progress indicator SHALL continue from where it was without restarting, and the upload SHALL complete normally
