## MODIFIED Requirements

### Requirement: RecordingRetentionJob.cleanup deletes WAV files older than threshold

The backend SHALL provide `packages/backend/meeting_playbook/retention/job.py` exporting an async function `cleanup(now: datetime, *, retention_days: int, recordings_dir: Path) -> int` that returns the count of WAV files actually deleted. The function SHALL:

1. Open a fresh `AsyncSession` via the application-wide session factory.
2. Select all `recording` rows where `created_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`. The selection SHALL NOT filter on `source`; both `source = 'live'` and `source = 'offline'` recordings SHALL be eligible for retention cleanup on the same 30-day clock.
3. For each matched row: attempt `Path(rec.file_path).unlink()` (skip if file already missing); on success, set `rec.deleted_at = now`. On `OSError` (permission / FS issues), log a warning, skip this row, do NOT set `deleted_at` (next sweep retries).
4. Commit all `deleted_at` updates in a single transaction.
5. Return the count of files actually unlinked or already-missing-but-now-marked.

The function SHALL be idempotent: running it twice in succession with the same `now` SHALL produce zero deletions on the second call (because all matched rows already have `deleted_at IS NOT NULL`).

#### Scenario: Cleanup deletes files older than threshold and marks rows

- **GIVEN** 3 recording rows: one with `created_at = now - 31 days` (file exists), one with `created_at = now - 5 days` (file exists), one with `created_at = now - 60 days` (file already deleted from disk by hand)
- **WHEN** `cleanup(now=now, retention_days=30, recordings_dir=...)` runs
- **THEN** the 31-day-old WAV file SHALL be deleted from disk; the 5-day-old WAV SHALL remain on disk; the 60-day-old row SHALL get `deleted_at = now` (file was already gone — self-heal); all 3 rows SHALL still exist in the DB; the 5-day-old row's `deleted_at` SHALL still be NULL

#### Scenario: Idempotent — second cleanup with same now is a no-op

- **GIVEN** a database state from the previous scenario (after first cleanup)
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs again immediately
- **THEN** zero additional file unlinks happen; the 5-day-old row's `deleted_at` is still NULL; no exceptions raised

#### Scenario: Transcripts and chat_messages are never touched

- **GIVEN** a meeting whose recording was just cleaned up
- **WHEN** the cleanup transaction commits
- **THEN** the meeting's `transcript_chunk` and `chat_message` rows SHALL be untouched (same row count + content as before)

#### Scenario: Offline-ingested recording is cleaned up on the same 30-day clock as live recordings

- **GIVEN** an offline-ingested recording row with `source = "offline"`, `created_at = now - 31 days`, `deleted_at IS NULL`, and the file present on disk
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** the offline WAV file SHALL be deleted from disk AND the row's `deleted_at` SHALL equal `now`; the `source` value SHALL NOT affect cleanup eligibility
