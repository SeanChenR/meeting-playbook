# TacticalAdvisor — agent notes

> Slice 8 (`slice-08-tactical-advisor`) outcome.
> Spec: `openspec/specs/tactical-advisor/spec.md` (after archive).
> Module: `packages/backend/meeting_playbook/advisor/`.

## What it does

`TacticalAdvisor.advise(...) -> AsyncIterator[str]` returns Vertex Gemini
Flash output token-by-token for a live meeting. Slice 8 ships the
button-only path (`Get Advice` in `AdvisorPane`); Slice 9 will reuse the
same Protocol with a populated `user_question` argument from the chatbox.

```python
class TacticalAdvisor(Protocol):
    async def advise(
        self,
        meeting_id: str,
        recent_chunks: list[TranscriptChunk],
        playbook: Playbook | None,
        me_display_name: str,
        counterparty_display_name: str,
        user_question: str | None,
        locale: Literal["zh-TW", "en"],
    ) -> AsyncIterator[str]: ...
```

The current implementation is `VertexFlashAdvisor` (`vertex_advisor.py`),
which calls `client.aio.models.generate_content_stream(...)` with a 15s
outer `asyncio.timeout` and a temperature of 0.4 / max 400 output tokens.

## Context assembly (per ADR-0018)

Each advice request gathers context from two sources:

1. **Last 60 seconds of transcript chunks** across both `me` and
   `counterparty` streams, fetched via
   `SessionRepository.list_chunks_last_60s(meeting_id)`. The window is a
   rolling SQL `started_at >= now() - INTERVAL '60 seconds'`, ordered
   ascending. Empty window → renders the localised placeholder
   `(無對話內容)` / `(no recent dialog)` so the model sees an explicit
   "no signal" marker rather than an empty section.
2. **Full playbook** (`PlaybookRepository.get_or_create_for_meeting`).
   Only the non-empty structured fields render as `## ${field}` sections;
   `free_form_markdown` is appended verbatim. Empty playbook → renders
   `(尚未填寫)` / `(empty playbook)`.

The system instruction is stable per locale (cache-friendly for Vertex's
system-instruction cache) and locks in the output rules: Markdown bullet
list, 3–5 items, ≤30 chars each, **bold** the most important phrase, and
the explicit "no signal" sentence to use when context is thin.

## Wire protocol — 4 new WS frames

Per the meeting-session spec MODIFIED requirement:

| Direction       | Frame             | Fields                                                        |
| --------------- | ----------------- | ------------------------------------------------------------- |
| client → server | `request_advice`  | `request_id`, `locale` (`zh-TW`\|`en`), `user_question?`     |
| server → client | `advice_chunk`    | `request_id`, `token`                                         |
| server → client | `advice_done`     | `request_id`                                                  |
| server → client | `advisor_failed`  | `request_id`, `error_code`, `message`                         |

`request_id` is a client-generated UUID; the server uses it to disambiguate
chunks from multiple historical advice requests in a single session
(`AdvisorPane` keeps history visible across requests).

## Error mapping

The router classifies advisor exceptions duck-typed by class name + message
fragments so it doesn't have to import `google.api_core.exceptions` at
module load time:

| Exception condition                                | `error_code`        |
| -------------------------------------------------- | ------------------- |
| `asyncio.TimeoutError` (15s outer cap)             | `advisor.timeout`   |
| `ResourceExhausted` / "quota" / "429"              | `advisor.quota`     |
| `Unauthenticated` / `PermissionDenied` / 401 / 403 | `advisor.auth`      |
| Any other `Exception`                              | `advisor.unknown`   |

`asyncio.CancelledError` re-raises silently (no frame) because the only
path that cancels an advice task is the WS handler shutting down on
`end_meeting` — emitting `advisor_failed` after the user pressed End would
look like a phantom error.

## Concurrency: separate AsyncSession per advice task

The capture / transcribe loop holds the request-scoped `AsyncSession` and
issues frequent commits (one INSERT per transcript chunk).
`AsyncSession` is **not** safe for concurrent use; if the advice task
shared the same session and tried to issue its own SELECT mid-write,
SQLAlchemy would raise `InvalidRequestError`.

The router's solution is `get_session_factory_dependency` — handlers that
spawn parallel sub-tasks inject the application-wide `async_sessionmaker`
and open a fresh session per task:

```python
async with session_factory() as advice_session:
    chunks = await SessionRepository(advice_session).list_chunks_last_60s(meeting_id)
    playbook = await PlaybookRepository(advice_session).get_or_create_for_meeting(meeting_id)
# Vertex stream runs OUTSIDE the session block — no DB conn held during the LLM call.
```

The integration test
`tests/sessions/test_router_advice.py::test_advice_during_active_capture_uses_separate_session`
runs concurrent capture + advice for ~5 seconds and asserts no
`InvalidRequestError` surfaces.

## Chat history (Slice 9)

Slice 9 added per-meeting persistence + a chatbox follow-up path on top
of the Slice 8 foundation. Persisted history is the byproduct of every
successful advice stream; failed/cancelled streams write nothing.

### Schema

```sql
CREATE TABLE chat_message (
  id          TEXT PRIMARY KEY,            -- cm_<token_urlsafe(16)>
  meeting_id  TEXT NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,               -- 'user' | 'advisor'
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (role IN ('user','advisor'))
);
CREATE INDEX chat_message_meeting_created_idx ON chat_message (meeting_id, created_at);
```

5 columns only — no `status` / `error_code` / `interrupted` because failed
advice doesn't write rows (Decision 2 in the slice-9 design.md).

### WS protocol additions

| Direction       | Frame             | Fields                                           |
| --------------- | ----------------- | ------------------------------------------------ |
| client → server | `chat_message`    | `request_id`, `content` (non-empty), `locale`    |

Response frames sticky from Slice 8: `advice_chunk` / `advice_done` /
`advisor_failed`. The chatbox path and the legacy `request_advice` button
path share the same response stream (just spawn `_run_advice` differently).

### Write strategy: INSERT-pair-on-success

`_run_advice` accumulates yielded tokens into `advisor_content`; on
successful stream completion (just before `advice_done` is sent), the
router calls `ChatMessageRepository.insert_pair_after_advice(meeting_id,
user_content, advisor_content)` in a fresh AsyncSession (separate from
the context-fetch session, separate from the request-scoped capture
session). Both rows commit atomically. The user row's `created_at` is
offset 1 microsecond earlier than the advisor row's so chronological
ordering stays deterministic.

Failed paths (`TimeoutError`, `ResourceExhausted`, `Unauthenticated`,
generic `Exception`, `CancelledError`) skip the INSERT entirely — the UI
shows a retry affordance from in-flight reducer state but no DB row
records the failure.

### Multi-turn context

`prompts._format_chat_history(messages, me_display_name, locale)` renders
prior chat_message rows as a `## 對話紀錄` (zh-TW) / `## Chat history`
(en) section between the 60s transcript and the final question line.
User rows render as `{me_display_name}: {content}`; advisor rows as
literal `Advisor: {content}` (NOT the counterparty display name —
conflating advisor with counterparty confuses the model). Empty history
omits the heading entirely.

### Frontend hydration + cache invalidation

`useMeetingSession` exposes `loadHistory(messages)` and
`onAdviceDone: ((requestId) => void) | null`. The route mounts both
React Query for `GET /api/meetings/{id}/chat_messages` and a session
callback registration:

```typescript
useEffect(() => {
  if (Array.isArray(chatMessagesQuery.data)) {
    session.loadHistory(chatMessagesQuery.data);
  }
}, [chatMessagesQuery.data, session]);

useEffect(() => {
  session.onAdviceDone = () => {
    queryClient.invalidateQueries({ queryKey: ["chat_messages", meetingId] });
  };
  return () => { session.onAdviceDone = null; };
}, [session, queryClient, meetingId]);
```

`HISTORY_LOADED` reducer case has an equality guard
(`if (state.advisor.messages === action.messages) return state;`) to
break the React render loop that would otherwise fire when the route's
`session` ref changes every render.

### In-flight UI state

Reducer keeps `advisor: { messages: ChatMessage[]; inFlight: ... | null }`.
The in-flight slice is local UI only — it carries `requestId`,
`userContent` (so the failed-state retry can resend it via the right
source path), `advisorTokens` (accumulated), `status`, and `source`
("button" | "chatbox"). Cleared on `advice_done`; the React Query refetch
then brings the persisted pair into `messages`.

### AdvisorPane layout (Decision 8)

```
┌─ Tactical advisor ────────┐
│ ChatMessageList (scrolls) │ ← persisted bubbles + virtual in-flight pair
│                            │
│ [ Get Advice ]              │ ← only in_progress
│ ───────────────────────── │
│ [ textarea ]    [ Send ]    │ ← only in_progress
└────────────────────────────┘
```

History stays visible across phases (so the user can review post-meeting);
input controls hide whenever `phase !== "in_progress"`.

### Cancel-previous policy

A new `chat_message` (or `request_advice`) frame while a prior advice is
in-flight cancels the prior task via `asyncio.Task.cancel()` (silent
re-raise of `CancelledError`, no `advisor_failed` sent). Since cancelled
streams don't write rows, the cancelled exchange leaves no DB trace.
