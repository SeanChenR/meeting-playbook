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

## Slice 9 upgrade path (chatbox)

The WS frame `request_advice.user_question` is **already wired through**
the entire stack:

- `RequestAdviceMessage` Pydantic model accepts an optional `user_question`.
- The router passes it straight through to `tactical_advisor.advise(...)`.
- `prompts.build_user_message` switches between the default question line
  ("請給出戰術建議。" / "Please give tactical advice.") and a
  custom-question line ("Sean 想問：…" / "Sean asks: …").

Slice 9 only needs to:

1. Add a chatbox UI inside `AdvisorPane` that sets `user_question` in the
   outbound `requestAdvice(...)` call (instead of leaving it `null`).
2. (Optional) widen the locale union if a third language is needed.

No backend / spec changes are expected.
