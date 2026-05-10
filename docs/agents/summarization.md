# MeetingSummarizer — agent notes

> Slice 10 (`slice-10-post-meeting-summary`) outcome.
> Spec: `openspec/specs/meeting-summary/spec.md` (after archive).
> Module: `packages/backend/meeting_playbook/summarization/`.

## What it does

`MeetingSummarizer.summarize(meeting_id) -> str` returns a 4-section
markdown summary of a completed meeting. Backend triggers it
automatically after `meeting_ended` (fire-and-forget background task)
and via `POST /api/meetings/{id}/summary` (manual regenerate). The
result is upserted into the `summary` table (1:1 with meeting). Frontend
fetches via `GET /api/meetings/{id}/summary` and renders inside the
detail page's Summary tab; users can regenerate or export to .md file.

```python
class MeetingSummarizer(Protocol):
    async def summarize(self, meeting_id: str) -> str: ...
```

The current implementation is `VertexProSummarizer`
(`vertex_summarizer.py`), wrapping
`client.aio.models.generate_content(...)` against Vertex Gemini 2.5 Pro
with a 90-second outer `asyncio.timeout`, temperature 0.3,
max 4096 output tokens.

## Schema (`summary` table)

```sql
CREATE TABLE summary (
  id            TEXT PRIMARY KEY,            -- sm_<token_urlsafe(16)>
  meeting_id    TEXT NOT NULL UNIQUE REFERENCES meeting(id) ON DELETE CASCADE,
  markdown      TEXT NOT NULL,
  generated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Four columns only — no `status` / `error_code` / `version` (slice-9
chat_message minimal-schema philosophy carries over). `UNIQUE (meeting_id)`
enforces 1:1; regeneration is a PostgreSQL `INSERT ... ON CONFLICT DO
UPDATE` upsert. Failed generation runs don't write rows; the UI's empty
or pending state covers the gap.

## Prompt structure (4 fixed sections)

System instruction enumerates the 4 required headings in document order
and forbids the model from changing heading text, skipping a section, or
inventing facts beyond the supplied context:

| zh-TW              | en                          |
| ------------------ | --------------------------- |
| `## 重點討論`      | `## Key discussion points`  |
| `## 決議`          | `## Decisions`              |
| `## Action items`  | `## Action items`           |
| `## 待解決問題`    | `## Open questions`         |

Action items render as `- [{owner_or_TBD}] {action}` — owner extraction
is the model's job based on transcript content; unknown owners default
to literal `TBD`.

User message section order: `## 會議基本資料` → `## Playbook` →
`## 整場 Transcript` → `## In-meeting Advisor 對話` (slice-9 chat
history). Empty playbook / chat history render the localised
`(尚未填寫)` / `(無)` placeholders.

After the LLM responds, `_validate_4_headings(markdown, locale)` does
case- and trim-insensitive substring matching for the 4 headings in
document order. Mismatch → `SummaryFormatError` → runtime treats it as
generation failure (no upsert).

## Auto-trigger (fire-and-forget)

`sessions/router.py::meeting_session_endpoint` calls
`summarization.runtime.spawn_summary_task(meeting_id)` AFTER the
`meeting_ended` frame is sent and the WebSocket is closed. The call is
NOT awaited — the user-facing UI already saw "ended" and we don't want
to delay the WS close handshake by 30-60s. Failures surface only via
`GET /summary` and the backend log.

```
[user clicks End] → end_meeting WS → finalize block → status=completed
                                                            │
                                            meeting_ended sent + WS close
                                                            │
                              spawn_summary_task() (fire-and-forget)
                                                            │
                              (background) summarizer.summarize(...) ~30-60s
                                                            │
                                       SummaryRepository.upsert(...)
                                                            │
                                       _inflight.pop(meeting_id)
```

## In-flight registry (concurrency)

`summarization/runtime.py` maintains a process-scoped
`dict[str, asyncio.Task]` mapping meeting_id to the in-flight task.
Concurrent spawn calls race-protect via `asyncio.Lock`. The spawned task
ALWAYS pops itself from the registry in its `finally` block — success,
exception, or cancellation. This guarantees the UI's pending → done /
not_found transition fires within one GET poll.

| Path                   | Behaviour                                      |
| ---------------------- | ---------------------------------------------- |
| First spawn            | Returns `True`, task registered                |
| Spawn while in-flight  | Returns `False`, no second task                |
| Successful completion  | Upserts row, pops registry, no exception       |
| `asyncio.TimeoutError` | Logs warning, no upsert, pops registry         |
| `SummaryFormatError`   | Logs warning, no upsert, pops registry         |
| Generic `Exception`    | Logs full traceback, no upsert, pops registry  |
| Cancellation           | Re-raises silently, pops registry              |
| Process restart        | Loses registry entirely; task dies; no row     |

Process restart safety: the task dies with the process, no row was
written, registry is empty → next `GET /summary` returns 404 → UI shows
empty state with regenerate button. State is consistent.

## HTTP surface (3-shape GET, busy-aware POST)

| Verb / Path | Response                                                  |
| ----------- | --------------------------------------------------------- |
| `POST /api/meetings/{id}/summary` | 202 `{status: pending}` on spawn; 409 `{error_code: summary.busy}` if in-flight; 404 `meeting.not_found` for non-owner |
| `GET /api/meetings/{id}/summary`  | 200 `Summary` (with `is_stale`) if row exists; 200 `{status: pending}` if no row but in-flight; 404 `summary.not_found` if neither |

Both endpoints require the gateway-injected `X-User-Id` header and
verify ownership via `MeetingRepository.get_for_user`.

The GET response NEVER embeds transcript / playbook / chat_message
data; clients fetch those separately if needed.

## `is_stale` SQL (Decision 9)

`SummaryRepository.get_with_stale_flag` runs a single query that
compares `summary.generated_at` against `MAX()` of the latest
`transcript_chunk.created_at`, `playbook.updated_at`, and
`chat_message.created_at`. A boolean column comes back in the result;
the GET endpoint passes it through verbatim:

```sql
SELECT
  s.id, s.meeting_id, s.markdown, s.generated_at,
  (
    s.generated_at < COALESCE((SELECT MAX(created_at) FROM transcript_chunk WHERE meeting_id = s.meeting_id), '-infinity'::timestamptz)
    OR s.generated_at < COALESCE((SELECT updated_at FROM playbook WHERE meeting_id = s.meeting_id), '-infinity'::timestamptz)
    OR s.generated_at < COALESCE((SELECT MAX(created_at) FROM chat_message WHERE meeting_id = s.meeting_id), '-infinity'::timestamptz)
  ) AS is_stale
FROM summary s
WHERE s.meeting_id = $1
```

The `COALESCE(..., '-infinity')` handles tables that are empty for the
meeting (so they never trigger stale).

## Frontend integration

- `lib/summary-api.ts` — `summaryQueryOptions(meetingId, opts)` with
  `refetchInterval` callback that polls every 1s while the response
  shape is `pending`; `regenerateSummary(meetingId)` for POST.
- `hooks/use-detail-tab.ts` — persists active tab to
  `localStorage["meeting-detail-tab:{meetingId}"]`. Falls back to
  `workspace` when persisted `summary` but meeting status isn't
  `completed`.
- `components/summary-pane.tsx` — 5 visual states (loading / pending /
  done / stale / empty), with regenerate + export buttons.
- `lib/markdown-export.ts` — `exportSummaryAsMarkdown(meeting, markdown)`
  uses File System Access API where supported; blob download fallback.
  Filename = `{meeting.title}-{YYYY-MM-DD}.md` with non-filesystem-safe
  characters (`/\:*?"<>|`) replaced by `_`. AbortError (user cancelled
  the save dialog) is respected — no fallback in that case.
- `routes/meetings/detail.tsx::DetailTabsView` — wraps the existing
  3-column workspace AND the SummaryPane inside `<Tabs>`. Workspace tab
  always enabled; Summary tab disabled (with localised hover hint)
  until `meeting.status === "completed"`.

## Trusted-context note

`MeetingRepository.get_by_id(meeting_id)` (slice-10 addition) bypasses
the ownership check and exists ONLY for the summarizer's background
context fetch. The auto-trigger spawns AFTER the WS handler validated
ownership; the POST endpoint validates ownership BEFORE spawning. Don't
use `get_by_id` from request-path endpoints — use `get_for_user` so a
user cannot read another user's meeting.
