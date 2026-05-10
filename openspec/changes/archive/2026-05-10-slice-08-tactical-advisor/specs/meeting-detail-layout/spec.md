## MODIFIED Requirements

### Requirement: Advisor pane shows a placeholder until the tactical advisor capability ships

The Advisor pane SHALL render the real `<AdvisorPane>` component (per the `tactical-advisor` capability spec) in both layout modes when the meeting session phase is `in_progress`. The placeholder text introduced in slice-7 round 1 (`meetings.detail.advisorPlaceholder`) is RETIRED — it MUST NOT appear once the meeting reaches `in_progress` phase. When the session phase is NOT `in_progress` (idle / connecting / ended / error), the pane SHALL render the empty-state hint described in the `tactical-advisor` spec (data-testid `advisor-pane-empty`) so the column never collapses to nothing in the columns layout.

#### Scenario: in_progress meeting renders the real AdvisorPane

- **GIVEN** a meeting whose WebSocket session has reached `in_progress`
- **WHEN** the detail page renders in either columns or stack mode
- **THEN** the Advisor pane SHALL contain a `Get Advice` button (per `tactical-advisor` spec) and SHALL NOT contain the legacy placeholder string from `meetings.detail.advisorPlaceholder`

#### Scenario: idle meeting still keeps the column populated with the empty state

- **GIVEN** a meeting in `scheduled` status whose session has not started
- **WHEN** the detail page renders in columns mode
- **THEN** the Advisor pane SHALL contain an element with `data-testid="advisor-pane-empty"` so the right column has visible content; it SHALL NOT contain a `Get Advice` button
