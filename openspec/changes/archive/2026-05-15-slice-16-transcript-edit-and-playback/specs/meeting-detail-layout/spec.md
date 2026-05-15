## ADDED Requirements

### Requirement: Meeting detail page renders MeetingAudioMiniPlayer pinned to the bottom

The meeting detail page (`packages/web/src/routes/meetings/detail.tsx`) SHALL render `<MeetingAudioMiniPlayer>` (defined in the `audio-playback` capability) as a persistent sticky bar at the bottom of the page in BOTH `columns` mode and `stack` mode. The mini-player SHALL NOT be placed inside any of the three panes (Playbook / Transcript / Advisor); it SHALL live in the page-level layout container below them. The mini-player SHALL remain visible regardless of which Tab is active when the Tabs UI is enabled (per the existing "Detail page wraps existing workspace in a Tabs UI" requirement). When no chunk has been selected for playback, the mini-player SHALL render in an idle state with the Play / Pause button disabled and the chunk-navigation buttons disabled; the Speed dropdown SHALL remain enabled so the user can pre-set their preferred speed before pressing ▶ on a chunk.

The mini-player's presence SHALL NOT alter the 30/40/30 grid widths defined in the columns-mode requirement, nor the P-T-A vertical ordering defined in the stack-mode requirement. The mini-player's height SHALL be reserved in the page layout so the bottom-most content of the active pane is NOT occluded by the mini-player bar.

#### Scenario: Mini-player renders in columns mode at the page bottom

- **GIVEN** a meeting detail page in columns mode with a viewport wider than 1024px
- **WHEN** the page renders
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL be present in the DOM below the three pane columns; its container SHALL have CSS `position: sticky; bottom: 0`; the three pane columns above SHALL retain the 30/40/30 widths

#### Scenario: Mini-player renders in stack mode below the three stacked panes

- **GIVEN** a meeting detail page in stack mode
- **WHEN** the page renders
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL be the last element in the page layout; the Playbook → Transcript → Advisor vertical order above it SHALL be unchanged

#### Scenario: Mini-player stays visible across Tab switches

- **GIVEN** a meeting detail page using the Tabs UI with Workspace tab currently active
- **WHEN** the user switches to the Summary tab
- **THEN** the `<MeetingAudioMiniPlayer>` SHALL still be visible in the DOM at the page bottom; if a chunk was playing the playback SHALL continue uninterrupted

#### Scenario: Idle mini-player has disabled play and navigation buttons

- **GIVEN** a freshly loaded meeting detail page where the user has NOT clicked ▶ on any chunk
- **WHEN** the page renders
- **THEN** the mini-player's Play/Pause button SHALL have the `disabled` attribute; the Previous and Next chunk buttons SHALL be disabled; the Speed dropdown SHALL be enabled and SHALL show the user's persisted `localStorage.miniPlayerRate` value (defaulting to `1.0x`)
