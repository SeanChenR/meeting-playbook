## ADDED Requirements

### Requirement: Meeting status transitions are atomic and only allowed in the forward direction

The repository SHALL provide `MeetingRepository.transition_status(meeting_id, expected_from, target)` as the SINGLE write path for the meeting `status` column. The transition SHALL succeed atomically (single SQL `UPDATE ... WHERE status = :expected_from RETURNING id`) so two concurrent attempts cannot both transition the same row. The only allowed transitions are:

- `scheduled → in_progress` (when a session starts)
- `in_progress → completed` (when a session ends)

Any other combination (backwards, skipping a state, repeating the current state) MUST raise `MeetingStatusConflict` carrying the requested transition and the actual current status. Direct `UPDATE meeting SET status = ...` SQL outside `transition_status` is forbidden in all production code paths.

#### Scenario: Allowed transition succeeds atomically

- **GIVEN** meeting `m_abc` has `status = "scheduled"`
- **WHEN** `MeetingRepository.transition_status("m_abc", expected_from="scheduled", target="in_progress")` is invoked
- **THEN** the row's status SHALL become `"in_progress"`, `updated_at` SHALL advance, and the call SHALL return successfully

#### Scenario: Backwards transition raises MeetingStatusConflict

- **GIVEN** meeting `m_abc` has `status = "completed"`
- **WHEN** `MeetingRepository.transition_status("m_abc", expected_from="in_progress", target="completed")` is invoked
- **THEN** the call SHALL raise `MeetingStatusConflict`, the row's status SHALL remain `"completed"`, and `updated_at` MUST NOT change

#### Scenario: Concurrent transition attempts are mutually exclusive

- **GIVEN** meeting `m_abc` has `status = "scheduled"` and two requests both attempt `scheduled → in_progress`
- **WHEN** both requests execute concurrently
- **THEN** exactly one SHALL succeed and exactly one SHALL raise `MeetingStatusConflict` (the second request observes status as already `in_progress`)

#### Scenario: Direct UPDATE bypassing transition_status is treated as a contract violation

- **WHEN** the meeting-domain source code is reviewed
- **THEN** there MUST be no `UPDATE meeting SET status` SQL anywhere outside `MeetingRepository.transition_status`; greppable enforcement is acceptable
