## ADDED Requirements

### Requirement: Export bundle MUST exclude recordings whose Recording row is soft-deleted

The per-meeting export bundle MUST treat `recording.deleted_at IS NOT NULL` as the authoritative signal that a WAV is no longer available, mirroring the cleanup-job invariant established by this capability. Any export path that assembles a bundle of meeting artefacts SHALL filter its Recording query to `deleted_at IS NULL` and SHALL NOT consult the filesystem as a fallback existence check. A soft-deleted Recording row SHALL NOT be re-included by any "if the file still happens to exist on disk" heuristic; the Recording window 30-day retention is a contract, not a hint. The Playbook, transcript, and Summary belonging to the meeting are unaffected and SHALL be included in the export regardless of any Recording row's `deleted_at` status, because those artefacts are not subject to the Recording window.

#### Scenario: Bundle excludes a Recording whose deleted_at is set

- **GIVEN** a meeting with two Recording rows: `counterparty` with `deleted_at IS NULL` and `me` with `deleted_at = 2026-03-01T00:00:00Z`
- **WHEN** the per-meeting export bundle is generated for this meeting
- **THEN** the bundle SHALL contain `recordings/counterparty.wav` and SHALL NOT contain `recordings/me.wav`, even if the `me.wav` file is still present on disk for any reason

#### Scenario: Bundle preserves transcript and summary even when every Recording is expired

- **GIVEN** a meeting whose every Recording row has `deleted_at IS NOT NULL` while its Playbook, TranscriptChunk rows, and Summary row remain in the database
- **WHEN** the export bundle is generated
- **THEN** the bundle SHALL contain `playbook.md`, `transcript.md`, and `summary.md` and SHALL NOT contain any entry under the `recordings/` prefix

#### Scenario: Filesystem fallback heuristic is forbidden

- **GIVEN** a Recording row whose `deleted_at IS NOT NULL` but whose `file_path` still resolves to an existing WAV on disk (cleanup raced with a manual restore)
- **WHEN** the export bundle is generated
- **THEN** that Recording SHALL be excluded from the bundle solely because of `deleted_at IS NOT NULL`; the bundle MUST NOT include the WAV based on filesystem existence
