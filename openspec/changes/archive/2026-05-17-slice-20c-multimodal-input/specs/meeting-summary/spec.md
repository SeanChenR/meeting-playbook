## MODIFIED Requirements

### Requirement: summary table persists per-meeting markdown summary

The backend SHALL provide a `summary` table (Alembic migration `0006_create_summary` plus migration `0014_add_attachment_hash_snapshot`) with exactly five columns: `id` (TEXT primary key, format `sm_<token>`), `meeting_id` (TEXT, NOT NULL, UNIQUE, foreign key to `meeting.id` ON DELETE CASCADE), `markdown` (TEXT, NOT NULL), `generated_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `now()`), and `attachment_hash_snapshot` (TEXT, NULL). The `UNIQUE (meeting_id)` constraint enforces a 1:1 relationship between meeting and summary. Deleting a `meeting` row SHALL cascade-delete the associated `summary` row.

The backend SHALL provide `SummaryRepository` at `packages/backend/meeting_playbook/summarization/repository.py` as the SOLE access path for `summary` rows. The repository SHALL expose `get_for_meeting(meeting_id) -> Summary | None`, `get_with_stale_flag(meeting_id) -> SummaryWithStale | None` (returns the row plus a computed `is_stale` boolean — see the "Summary is_stale flag" requirement for the full computation), and `upsert(meeting_id, markdown, attachment_hash_snapshot) -> Summary` (uses PostgreSQL `INSERT ... ON CONFLICT (meeting_id) DO UPDATE SET markdown = EXCLUDED.markdown, generated_at = now(), attachment_hash_snapshot = EXCLUDED.attachment_hash_snapshot RETURNING *`). The repository SHALL NOT expose any delete method.

#### Scenario: summary row cascade-deletes with the parent meeting

- **GIVEN** a meeting with one `summary` row
- **WHEN** the meeting row is deleted
- **THEN** the `summary` row SHALL be deleted by FK cascade

#### Scenario: upsert replaces existing markdown atomically and updates attachment_hash_snapshot

- **GIVEN** a meeting whose summary was generated yesterday with markdown "v1" and `attachment_hash_snapshot = "h_old"`
- **WHEN** `repo.upsert(meeting_id, markdown="v2", attachment_hash_snapshot="h_new")` runs
- **THEN** the database SHALL contain exactly one summary row for the meeting with `markdown = "v2"`, `generated_at` updated to now (within 1 second tolerance), AND `attachment_hash_snapshot = "h_new"`

#### Scenario: get_for_meeting on missing summary returns None

- **GIVEN** a meeting that has never been summarized
- **WHEN** `repo.get_for_meeting(meeting_id)` runs
- **THEN** the call SHALL return `None`

#### Scenario: Legacy rows with NULL attachment_hash_snapshot remain readable

- **GIVEN** a `summary` row written before this migration with `attachment_hash_snapshot IS NULL`
- **WHEN** `repo.get_for_meeting(meeting_id)` runs
- **THEN** the call SHALL succeed and the returned `Summary.attachment_hash_snapshot` attribute SHALL be `None`


### Requirement: MeetingSummarizer module exposes a single coroutine summarize()

The backend SHALL provide a `MeetingSummarizer` Protocol (and a concrete `VertexProSummarizer` implementation) located at `packages/backend/meeting_playbook/summarization/`. The Protocol's single coroutine `summarize(meeting_id: str) -> SummaryGenerationResult` SHALL return a dataclass containing `markdown: str` (the full summary text) AND `attachment_hash_snapshot: str` (hex SHA-256 of the attachment set seen during generation, equal to the canonical empty-set hash when zero attachments are present). The Protocol SHALL be the SOLE entry point used by `summarization/runtime.py` to invoke the underlying LLM; no other module SHALL import any Vertex / `google-genai` symbol directly.

The concrete `VertexProSummarizer` SHALL wrap the official `google-genai` SDK against Vertex AI. The model id SHALL come from `Settings.vertex_pro_model_id` (default `gemini-2.5-pro`). The implementation SHALL apply a 90-second outer `asyncio.timeout` so a hung Vertex stream raises `asyncio.TimeoutError` rather than blocking the background task indefinitely. The implementation SHALL fetch context (transcript chunks via `SessionRepository.list_chunks_for_meeting`, playbook via `PlaybookRepository.get_or_create_for_meeting`, chat history via `ChatMessageRepository.list_for_meeting`, and attachments via `MeetingAttachmentRepository.list_for_meeting`) inside its own `async with session_factory() as ...` scope; the LLM call itself SHALL run OUTSIDE the session block (no DB connection held during the LLM round-trip).

The implementation SHALL pass the assembled `MultimodalContext.parts` to `client.models.generate_content(contents=parts, ...)` when at least one attachment was successfully processed; otherwise it SHALL pass the legacy single-text-string `contents` to preserve identical behaviour to the pre-S20c implementation.

The implementation SHALL validate that the returned markdown contains exactly four required headings (case- and trim-insensitive match) in fixed order. Missing or out-of-order headings SHALL raise `SummaryFormatError`; the runtime treats this same as a Vertex failure (no upsert).

#### Scenario: summarize returns markdown with all four required sections and an attachment hash

- **GIVEN** a mocked Vertex client returning markdown that contains "## 重點討論", "## 決議", "## Action items", and "## 待解決問題" in order AND a meeting with one PDF attachment whose bytes hash to `h_pdf`
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL return `SummaryGenerationResult(markdown=<the markdown verbatim>, attachment_hash_snapshot=sha256(sorted([h_pdf])))`

#### Scenario: summarize with zero attachments returns the canonical empty-set hash

- **GIVEN** a mocked Vertex client returning valid markdown AND a meeting with zero attachments
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the returned `attachment_hash_snapshot` SHALL equal `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`

#### Scenario: summarize with mixed image and PDF passes Part list to Vertex

- **GIVEN** a meeting with one PNG attachment and one PDF attachment
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the `contents` argument passed to `client.models.generate_content(...)` SHALL be a `list[Part]` whose first element is `Part.from_bytes(data=<png bytes>, mime_type="image/png")` and whose subsequent text part contains both the PDF-extracted text and the transcript / playbook / chat sections

#### Scenario: 90-second cap on Vertex call raises TimeoutError

- **GIVEN** a mocked Vertex client that sleeps 100 seconds before returning AND any attachment configuration
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `asyncio.TimeoutError` between 90.0 and 92.0 seconds after invocation

#### Scenario: Missing required heading raises SummaryFormatError

- **GIVEN** a mocked Vertex client returning markdown that omits the "## 決議" heading
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `SummaryFormatError` (which the runtime catches and treats as a generation failure — no upsert, log warning, pop in-flight)

#### Scenario: A corrupt PDF among attachments is skipped, not fatal

- **GIVEN** a meeting with one good PNG and one corrupt PDF that raises during `pypdf` extraction
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the Vertex call SHALL succeed with `contents` containing the good PNG part plus a text part assembled from the remaining context, the returned `attachment_hash_snapshot` SHALL hash only the good PNG, AND a structured warning naming the corrupt PDF's `attachment_id` and `error_code = "attachment.extraction_failed"` SHALL be logged


### Requirement: Summary generation runtime serializes per-meeting work via in-process registry

The backend SHALL provide `summarization/runtime.py` exposing `spawn_summary_task(meeting_id) -> bool` and `is_pending(meeting_id) -> bool`. The module SHALL maintain a process-scoped `dict[str, asyncio.Task]` mapping meeting_id to the in-flight summary task; access SHALL be guarded by an `asyncio.Lock` to prevent races between concurrent spawn calls. `spawn_summary_task` SHALL return `True` and create a new task when no in-flight task exists for the meeting; SHALL return `False` (no new task created) when an in-flight task is present and not done. `is_pending` SHALL return `True` iff the registry holds an unfinished task for the meeting.

The spawned task SHALL invoke `MeetingSummarizer.summarize(meeting_id)`, then `SummaryRepository.upsert(meeting_id=..., markdown=result.markdown, attachment_hash_snapshot=result.attachment_hash_snapshot)` on success. On any exception (`asyncio.TimeoutError`, `SummaryFormatError`, generic `Exception`) the task SHALL log the full traceback via `logger.exception` and SHALL NOT call `upsert`. The task's `finally` clause SHALL pop the meeting_id from the registry regardless of outcome.

Process restart loses the in-flight registry entirely; this is acceptable because the task itself dies with the process and no row was written, leaving a consistent "no summary, can regenerate" UI state.

#### Scenario: Successful generation upserts markdown + snapshot then pops registry

- **GIVEN** a registered task running `summarizer.summarize("m_x")` that returns `SummaryGenerationResult(markdown="...", attachment_hash_snapshot="h_x")`
- **WHEN** the task completes
- **THEN** the database SHALL contain a `summary` row for "m_x" whose `markdown` and `attachment_hash_snapshot` match the result AND `is_pending("m_x")` SHALL return `False`

#### Scenario: Concurrent spawn calls — second returns False without creating a task

- **GIVEN** an empty registry
- **WHEN** two coroutines call `spawn_summary_task("m_x")` simultaneously
- **THEN** exactly one call SHALL return `True` and create a task; the other call SHALL return `False`

#### Scenario: Failed generation skips upsert but still pops registry

- **GIVEN** a registered task whose `summarize` raises `asyncio.TimeoutError`
- **WHEN** the task's exception path runs
- **THEN** the database SHALL have ZERO new `summary` rows for the meeting AND `is_pending("m_x")` SHALL return `False` AND the backend log SHALL contain the traceback


## ADDED Requirements

### Requirement: Summary is_stale flag reacts to attachment set changes

`SummaryRepository.get_with_stale_flag(meeting_id) -> SummaryWithStale | None` SHALL compute `is_stale: bool` as `True` when ANY of the following hold:

1. The latest `transcript_chunk.created_at` for the meeting is later than `summary.generated_at`.
2. The latest `playbook.updated_at` for the meeting is later than `summary.generated_at`.
3. The latest `chat_message.created_at` for the meeting is later than `summary.generated_at`.
4. The current attachment-set hash for the meeting differs from `summary.attachment_hash_snapshot`. The current attachment-set hash is computed as `sha256(sorted(sha256(open(att.file_path,'rb').read()) for att in MeetingAttachmentRepository.list_for_meeting(meeting_id) if att.deleted_at IS NULL))`, expressed as a lowercase hex string. The empty-attachment set SHALL hash to the canonical empty-set hash `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`.

Legacy rows where `attachment_hash_snapshot IS NULL` SHALL be treated as if they recorded the canonical empty-set hash — so a legacy summary for a meeting with zero attachments is NOT stale on the attachment axis, but a legacy summary for a meeting with one or more current attachments IS stale.

#### Scenario: Adding a new attachment marks the summary stale

- **GIVEN** a meeting with one PDF whose summary was generated with `attachment_hash_snapshot` matching the one-PDF hash AND no transcript / playbook / chat changes since generation
- **WHEN** a second PNG attachment is uploaded AND `get_with_stale_flag(meeting_id)` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Deleting an attachment marks the summary stale

- **GIVEN** a meeting whose summary was generated with two attachments and snapshot hash matches that set
- **WHEN** one attachment is soft-deleted and `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Replacing an attachment with byte-identical content does NOT mark stale

- **GIVEN** a meeting whose summary was generated with one PDF whose bytes hash to `h_pdf`
- **WHEN** the user deletes that attachment and uploads a different `AttachmentRef` whose file bytes are byte-identical
- **THEN** the current attachment-set hash SHALL still equal `attachment_hash_snapshot` AND `is_stale` SHALL be `False` (provided no other axis triggers)

#### Scenario: Legacy NULL snapshot row with no current attachments is NOT stale on the attachment axis

- **GIVEN** a summary row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has zero non-deleted attachments AND no other axis is newer than `generated_at`
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with current attachments IS stale

- **GIVEN** a summary row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has one PDF attachment
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`


### Requirement: Summary pane shows a localized stale banner when attachments change

The frontend `<SummaryPane>` component at `packages/web/src/components/summary-pane.tsx` SHALL render a stale banner above the markdown body whenever the GET `/api/meetings/{id}/summary` response body has `is_stale === true`. The banner SHALL contain (a) localized text retrieved via `t("summary.stale.attachments_changed")` and (b) a button labeled via `t("summary.stale.regenerate_button")` that POSTs to `/api/meetings/{id}/summary` to trigger regeneration. The locale files `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` SHALL both contain the keys `summary.stale.attachments_changed` and `summary.stale.regenerate_button` (the `locales.test.ts` deep-equal test SHALL pass).

The banner SHALL NOT show when `is_stale === false`, and SHALL NOT show when the GET response is the pending shape (`{status: "pending", generated_at: null}`).

#### Scenario: is_stale true renders the localized banner

- **GIVEN** GET `/api/meetings/m_x/summary` returns `{id, meeting_id, markdown, generated_at, is_stale: true}` in the zh-TW locale
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL contain the localized text from `summary.stale.attachments_changed` (zh-TW) AND a button whose text equals the localized text from `summary.stale.regenerate_button`

#### Scenario: is_stale false hides the banner

- **GIVEN** the GET response has `is_stale: false`
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL NOT contain the localized stale banner text

#### Scenario: Pending response hides the banner

- **GIVEN** the GET response is `{status: "pending", generated_at: null}`
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL NOT contain the localized stale banner text (the pending UI is rendered instead)
