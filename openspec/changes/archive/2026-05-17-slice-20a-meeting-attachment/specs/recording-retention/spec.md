## MODIFIED Requirements

### Requirement: RecordingRetentionJob.cleanup deletes WAV files older than threshold

The backend SHALL provide `packages/backend/meeting_playbook/retention/job.py` exporting an async function `cleanup(now: datetime, *, retention_days: int, recordings_dir: Path, attachments_dir: Path) -> int` that returns the count of files (WAV and attachment combined) actually deleted. The function SHALL:

1. Open a fresh `AsyncSession` via the application-wide session factory.
2. Select all `recording` rows where `created_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`.
3. For each matched recording row: attempt `Path(rec.file_path).unlink()` (skip if file already missing); on success, set `rec.deleted_at = now`. On `OSError` (permission / FS issues), log a warning, skip this row, do NOT set `deleted_at` (next sweep retries).
4. Select all `meeting_attachment` rows where `uploaded_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`.
5. For each matched attachment row: attempt `Path(att.file_path).unlink()` (skip if file already missing); on success, set `att.deleted_at = now`. On `OSError`, log a warning, skip this row, do NOT set `deleted_at`.
6. Commit all `deleted_at` updates (both recording and attachment) in a single transaction.
7. Return the count of files actually unlinked or already-missing-but-now-marked, summed across both tables.

The function SHALL be idempotent: running it twice in succession with the same `now` SHALL produce zero deletions on the second call (because all matched rows already have `deleted_at IS NOT NULL`). An exception while processing one row (recording or attachment) SHALL NOT abort the entire transaction; the row is skipped, the loop continues, and successful rows are committed.

#### Scenario: Cleanup deletes recording files older than threshold and marks rows

- **GIVEN** 3 recording rows: one with `created_at = now - 31 days` (file exists), one with `created_at = now - 5 days` (file exists), one with `created_at = now - 60 days` (file already deleted from disk by hand), and zero `meeting_attachment` rows
- **WHEN** `cleanup(now=now, retention_days=30, recordings_dir=..., attachments_dir=...)` runs
- **THEN** the 31-day-old WAV file SHALL be deleted from disk; the 5-day-old WAV SHALL remain on disk; the 60-day-old row SHALL get `deleted_at = now` (file was already gone — self-heal); all 3 rows SHALL still exist in the DB; the 5-day-old row's `deleted_at` SHALL still be NULL; the function SHALL return `2`

#### Scenario: Cleanup deletes attachment files older than threshold and marks rows

- **GIVEN** zero recording rows and 3 `meeting_attachment` rows: one with `uploaded_at = now - 31 days` (file exists), one with `uploaded_at = now - 5 days` (file exists), one with `uploaded_at = now - 45 days` (file already missing from disk)
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** the 31-day-old attachment file SHALL be deleted from disk; the 5-day-old attachment SHALL remain; the 45-day-old row SHALL get `deleted_at = now`; all 3 `meeting_attachment` rows SHALL still exist; the function SHALL return `2`

#### Scenario: Cleanup processes recordings and attachments together

- **GIVEN** 2 recording rows older than 30 days (both files present) and 2 `meeting_attachment` rows older than 30 days (both files present), all with `deleted_at IS NULL`
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** all 4 files SHALL be removed from disk; all 4 rows SHALL have `deleted_at = now`; the function SHALL return `4`

#### Scenario: Idempotent — second cleanup with same now is a no-op

- **GIVEN** a database state where every row older than the threshold already has `deleted_at` set
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs again immediately
- **THEN** zero additional file unlinks happen; no row's `deleted_at` is changed; no exceptions are raised; the function SHALL return `0`

#### Scenario: Transcripts and chat_messages are never touched

- **GIVEN** a meeting whose recording and attachment were just cleaned up
- **WHEN** the cleanup transaction commits
- **THEN** the meeting's `transcript_chunk` and `chat_message` rows SHALL be untouched (same row count + content as before)

#### Scenario: One row's unlink failure does not abort the transaction

- **GIVEN** 2 attachment rows older than 30 days where the first row's file path raises `PermissionError` on unlink and the second row's file unlinks successfully
- **WHEN** `cleanup(...)` runs
- **THEN** the first row's `deleted_at` SHALL remain NULL (retry next sweep), the second row's `deleted_at` SHALL be set, the function SHALL return `1`, and the loop SHALL log the permission error without propagating

### Requirement: Retention job runs every 24 hours via FastAPI lifespan

The backend SHALL provide `packages/backend/meeting_playbook/retention/runtime.py` exporting `run_forever(*, settings: Settings) -> None` that runs an infinite `asyncio` loop: at the top of each iteration call `cleanup(now=datetime.now(UTC), retention_days=settings.recording_retention_days, recordings_dir=Path(settings.recordings_dir).expanduser(), attachments_dir=Path(settings.attachment_dir).expanduser())`, then `await asyncio.sleep(24 * 3600)`. Exceptions inside the iteration SHALL be caught (except `asyncio.CancelledError` which re-raises) and logged via `logger.exception`; the loop SHALL continue.

The FastAPI app SHALL register a `lifespan` async context manager that spawns `run_forever` as a background `asyncio.Task` on startup and cancels it on shutdown (with `asyncio.CancelledError` suppressed during the await of the cancelled task).

#### Scenario: First cleanup runs immediately on backend startup

- **GIVEN** a backend that just booted with `RECORDING_RETENTION_DAYS = 30` and `ATTACHMENT_DIR` configured
- **WHEN** the lifespan startup hook fires
- **THEN** within 1 second `cleanup` SHALL have been invoked exactly once with both `recordings_dir` and `attachments_dir` arguments

#### Scenario: Subsequent cleanups run on a 24-hour cadence

- **GIVEN** a running backend with retention loop active
- **WHEN** 24 hours pass
- **THEN** a second `cleanup` invocation SHALL fire with the same argument signature

#### Scenario: Cleanup exception does NOT kill the loop

- **GIVEN** a stub `cleanup` that raises `RuntimeError("disk full")` on first call but succeeds on second
- **WHEN** the loop runs through two iterations
- **THEN** the first iteration SHALL log the exception traceback; the second iteration SHALL execute and succeed; the loop SHALL still be alive

#### Scenario: Lifespan shutdown cancels the loop cleanly

- **GIVEN** a running backend with retention loop active
- **WHEN** the FastAPI app shuts down
- **THEN** the lifespan finalizer SHALL cancel the task and await it; the await SHALL complete without raising (CancelledError suppressed); shutdown SHALL not hang

## ADDED Requirements

### Requirement: ATTACHMENT_DIR configuration with documented default

The `Settings` class in `packages/backend/meeting_playbook/config.py` SHALL gain a new field `attachment_dir: str = "~/MeetingPlaybook/attachments"` (read from env var `ATTACHMENT_DIR` per pydantic-settings convention). The directory SHALL be created lazily on first upload if it does not exist. The `.env.example` file SHALL document the option (commented-out line referencing ADR-0020 and noting that attachments share the same retention window as recordings).

#### Scenario: Default attachment directory is `~/MeetingPlaybook/attachments`

- **GIVEN** no `ATTACHMENT_DIR` env var set
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.attachment_dir` SHALL equal `"~/MeetingPlaybook/attachments"`

#### Scenario: Override via env var takes effect

- **GIVEN** env var `ATTACHMENT_DIR = /tmp/test-attachments`
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.attachment_dir` SHALL equal `"/tmp/test-attachments"`
