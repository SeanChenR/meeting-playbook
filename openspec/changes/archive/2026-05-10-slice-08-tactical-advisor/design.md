## Context

Slice 6 (mic-only transcript) + Slice 7 (BlackHole dual-stream) put both halves of the in-meeting audio path into production. Slice 5 (Calendar import + Vertex Pro playbook generation) put the playbook authoring path in. Slice 8 connects them: while a session runs, the user clicks "Get Advice" → backend assembles the last 60 seconds of dual-speaker transcript + the user's playbook → Vertex Gemini Flash streams a tactical Markdown reply → the AdvisorPane on the right side of the detail page renders it token-by-token.

ADR-0017 already locked the trigger model (button + chatbox; chatbox is Slice 9). ADR-0018 already locked the context recipe (last 60s + full playbook; rolling summary deferred to v2). ADR-0006 already locked Vertex AI as the LLM provider with Flash for in-meeting + Pro for batch generation.

This slice is the foundation for Slice 9 (chatbox follow-up) and Slice 10 (post-meeting summary). The contract decisions made here — `request_advice` frame shape, TacticalAdvisor module signature, error code namespace, in-flight task lifecycle — are re-read by both. Over-invest in a clean WS frame contract and a `TacticalAdvisor.advise()` signature that already accepts `user_question` (Slice 9) and `locale` (already needed in Slice 8); under-invest in advice persistence (Slice 8 keeps it ephemeral; Slice 9 chatbox decides whether to add a chat_message table).

## Goals / Non-Goals

**Goals:**

- Click "Get Advice" → first `advice_chunk` frame arrives within ~5 seconds (target, not asserted)
- Streaming UX: each Vertex SDK chunk forwards as one `advice_chunk` frame; AdvisorPane appends tokens to the active card with smooth scroll-to-bottom
- Context assembly is correct: last 60s window via SQL `started_at >= now() - 60s`, both speakers labelled by display name, only non-empty playbook fields
- Failure surfaces inline on the failing card with a `重試` / `Retry` button; never silently drops; never closes the WS
- AdvisorPane state survives across multiple Get Advice clicks within one meeting session (chat-style append, newest at bottom)
- TacticalAdvisor runs concurrent with capture/transcribe without contending the SQLAlchemy AsyncSession (separate session per advice task)
- WS contract preserves Slice 9 forward-compat: `request_advice` accepts `user_question?: str` and `locale: "zh-TW"|"en"` from day one

**Non-Goals:**

- Chatbox follow-up — Slice 9
- Auto-trigger advice every 30s — explicitly rejected in ADR-0017
- Persisting advice cards across page reload — purely client React state
- Cancel-previous-advice when a new one is requested — Slice 8 disables the button, so it cannot happen
- DSP-level prompt caching — relies on Gemini's built-in system_instruction cache; no manual cache layer
- Multi-language LLM auto-detect — locale is taken from `i18n.language`, not transcript
- Advice writes to `transcript_chunk` or any other DB row — strictly ephemeral
- Switching Vertex provider per meeting — not in scope; Vertex is the only LLM (ADR-0006)

## Decisions

### Streaming protocol: per-SDK-chunk WS frame, transparent forwarding

The Vertex `google-genai` SDK's `generate_content_stream()` yields `chunk.text` segments that are NOT individual tokens — they are natural breakpoints (≈ 5–20 tokens each). Forward each SDK chunk as one `advice_chunk` WS frame.

```python
async for chunk in client.aio.models.generate_content_stream(model=..., contents=...):
    if chunk.text:
        await send(AdviceChunkMessage(request_id=request_id, token=chunk.text))
```

A typical Flash response of ~200 characters produces ~30–50 frames. The frontend reducer appends `token` to the active card's accumulated text. WebSocket per-connection write ordering is guaranteed by Starlette's underlying queue (single coroutine writes), so frames arrive in order.

**Rejected**: per-token batching, sentence-batched forwarding. Single token would over-frame; sentence batching loses streaming feel.

### Context assembly: SQL window + dialogue format + non-empty playbook

`SessionRepository.list_chunks_last_60s(meeting_id) -> list[TranscriptChunk]`:

```sql
SELECT * FROM transcript_chunk
 WHERE meeting_id = :mid
   AND started_at >= now() - INTERVAL '60 seconds'
 ORDER BY started_at ASC
```

If the result is empty (silent meeting / just started), the prompt's "最近 60 秒對話" section says `(無對話內容)` and the system_instruction tells the model "if no actionable signal, say so honestly".

Dialogue format renders the chunks as `{display_name}：{text} ({HH:mm:ss})`, where `display_name` is `meeting.me_display_name` for `speaker = "me"` and `meeting.counterparty_display_name` for `speaker = "counterparty"`. No XML / JSON wrapping.

Playbook is fetched fresh on each advice request (not cached on the session). Only non-empty structured fields are interpolated into the prompt; if all 6 structured fields are empty, only `free_form_markdown` (if non-empty) shows. Empty playbook → prompt says `(尚未填寫)`.

### Prompt structure: system_instruction + user message, Markdown bullet output

System instruction (locale-aware) is a stable string per locale; user message is rebuilt per request with playbook + transcript:

```
[system_instruction]
You are Sean's tactical sales advisor for live B2B meetings.
{LOCALE_INSTRUCTION[locale]}
Output rules:
- Format: Markdown bullet list, 3-5 items, each ≤ 30 characters.
- Tone: 直白、可立即執行 (immediately actionable). Avoid platitudes.
- Use **bold** to highlight the single most important phrase.
- If the recent dialog gives no actionable signal, say so honestly:
  「目前對話無明顯戰術點，可主動推進議題。」
- NEVER invent facts not in the playbook or transcript.

[user_message]
## 會議 playbook
{non-empty structured fields, Markdown headings}
{free_form_markdown if non-empty}

## 最近 60 秒對話
{display_name}：{text} ({HH:mm:ss})
...

請給出戰術建議。     <- when user_question is None (Slice 8)
Sean 想問：{user_question}\n請根據以上 context 回答。    <- Slice 9
```

`LOCALE_INSTRUCTION = {"zh-TW": "請用繁體中文（zh-TW）回答。", "en": "Reply in English."}`.

Generation params: `temperature=0.4`, `max_output_tokens=400`, default `top_p`. The 400 ceiling is a safety net for runaway generation; the 3-5 bullet rule is enforced primarily by prompt instruction.

### request_advice forward-compatibility (Slice 9 chatbox)

The `request_advice` Pydantic model already includes `user_question: str | None = None` and `locale: Literal["zh-TW", "en"] = "zh-TW"`, even though Slice 8's UI only sends the request without a `user_question`. This means Slice 9 (chatbox) does not change the WS contract — it only changes what the frontend sends and which prompt branch fires:

```python
def _build_user_message(playbook, chunks, user_question):
    if user_question is None:
        question_line = "請給出戰術建議。"
    else:
        question_line = f"Sean 想問：{user_question}\n請根據以上 context 回答。"
    return f"## 會議 playbook\n{playbook_md}\n\n## 最近 60 秒對話\n{transcript_md}\n\n{question_line}"
```

### In-flight requests: button-disable, end_meeting cancels in-flight

Frontend invariant: the `Get Advice` button is disabled from the moment `request_advice` is sent until either `advice_done` or `advisor_failed` arrives. So at most one advice request is in-flight per session at any time. This also means `request_id` is in practice always unique-and-current; the field exists for Slice 9 chatbox queue UX, not Slice 8 disambiguation.

Backend keeps a `advice_task: asyncio.Task | None` slot in the WS handler closure. On `request_advice`:

```python
# Defensive: if the previous advice task is somehow still running, cancel it.
if advice_task and not advice_task.done():
    advice_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await advice_task
advice_task = asyncio.create_task(
    _run_advice(msg.request_id, msg.user_question, msg.locale),
    name=f"advice-{msg.request_id}",
)
```

On `end_meeting` or client disconnect, the finalize block cancels any in-flight `advice_task` before closing the WS:

```python
if advice_task and not advice_task.done():
    advice_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await advice_task
```

### PlaybookPane stays read-write during in_progress; LLM reads DB-saved version

PlaybookPane already has no readonly flag and the playbook PUT endpoint does not gate on `meeting.status`, so editing during a session already works. No code change required for editability itself; this slice only **confirms** it via a test that fires a PUT during an active WS session and asserts the existing `_write_lock` does not contend (different AsyncSession).

The LLM context fetches `playbook` from the database at the moment of the advice request. So an unsaved textarea draft is invisible to the model — the user must press `Save` first if they want their edits to influence the next advice. This is the documented behavior; no in-memory bridge from the frontend draft to the backend prompt.

### AdvisorPane state: chat-style append, ephemeral, scroll-to-bottom

AdvisorPane reducer state shape (held inside `useMeetingSession` for cohesion with the rest of session state):

```ts
type AdviceRequest = {
  requestId: string;
  startedAt: string; // ISO
  status: "streaming" | "done" | "failed";
  tokens: string;    // accumulated text, rendered via <MarkdownPreview source={tokens} />
  error?: { code: string; message: string };  // when status === "failed"
};

type AdvisorState = {
  requests: AdviceRequest[];   // in click order; UI renders top-to-bottom
};
```

Reducer actions:

- `ADVICE_REQUESTED { requestId }` → push `{ requestId, status: "streaming", tokens: "" }`
- `ADVICE_TOKEN { requestId, token }` → append `token` to the matching request's `tokens`
- `ADVICE_DONE { requestId }` → flip status to `done`
- `ADVICE_FAILED { requestId, code, message }` → flip status to `failed`, store error
- (no `ADVICE_RETRY` — retry sends a fresh `request_advice` with a new requestId)

UI:

- A vertical list of cards, oldest at top, newest at bottom
- Each card: header row `{HH:mm} • 戰術建議` + `<MarkdownPreview source={tokens} />` body
- Streaming card shows a small "思考中…" indicator next to the timestamp until status flips
- Failed card shows error message + `重試` button
- AdvisorPane scrolls to the latest card on `ADVICE_REQUESTED` and on `ADVICE_TOKEN` (smooth scroll, debounced)
- The `Get Advice` button at the bottom of the pane is disabled when `requests.at(-1)?.status === "streaming"`
- On `phase` ≠ `in_progress` → AdvisorPane shows an empty state with a localised hint, button hidden

State is purely client; clearing the page or ending the meeting drops it. No DB schema for advice in Slice 8.

### Error handling: typed advisor_failed frame, mapped error codes

Backend catches every exception in `_run_advice` and converts to a typed frame:

| Backend exception | error_code | i18n key |
| --- | --- | --- |
| `asyncio.TimeoutError` (15s outer cap) | `advisor.timeout` | `errors.advisor.timeout` |
| Vertex `google.api_core.exceptions.ResourceExhausted` (429) | `advisor.quota` | `errors.advisor.quota` |
| Vertex `google.api_core.exceptions.Unauthenticated` (401) | `advisor.auth` | `errors.advisor.auth` |
| Other `Exception` | `advisor.unknown` | `errors.common.unknown` |

```python
async def _run_advice(request_id, user_question, locale):
    try:
        async with asyncio.timeout(15):
            async for token in tactical_advisor.advise(...):
                await _send(AdviceChunkMessage(request_id=request_id, token=token))
        await _send(AdviceDoneMessage(request_id=request_id))
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        await _send(AdvisorFailedMessage(request_id=request_id,
            error_code="advisor.timeout", message="..."))
    except ResourceExhausted as exc:
        await _send(AdvisorFailedMessage(request_id=request_id,
            error_code="advisor.quota", message=str(exc)))
    ...
```

`advisor_failed` does NOT close the WS — the meeting session continues normally; only the failing advice card is marked. Generic `error` frame (which DOES close the WS) is reserved for unrecoverable session-level failures.

### Locale: tracked via request_advice.locale field

Frontend reads `i18n.language` (`"zh-TW"` or `"en"`) at the moment of the click and includes it in the `request_advice` frame. Backend uses it to pick `LOCALE_INSTRUCTION[locale]` for the system_instruction. This means switching the UI language between two clicks switches the advice language for the next request — no model restart, no special handling.

The `locale` field on `request_advice` is required (not optional) with a default of `"zh-TW"` so old client that doesn't include it still works. New WS clients in this slice always include it explicitly.

### Concurrency: separate AsyncSession for advisor task

A new FastAPI dependency `get_session_factory_dependency` returns the application-wide `async_sessionmaker[AsyncSession]`. The session WS handler holds it as a closure variable; `_run_advice` opens its own session for the duration of its work:

```python
async def _run_advice(request_id, user_question, locale):
    async with session_factory() as advice_session:
        session_repo = SessionRepository(advice_session)
        playbook_repo = PlaybookRepository(advice_session)
        chunks = await session_repo.list_chunks_last_60s(meeting_id)
        playbook = await playbook_repo.get_for_meeting(meeting_id)
    # advice_session closed BEFORE the long Vertex stream — don't hold a DB
    # connection open for 5–10 seconds of LLM I/O.
    ...vertex stream loop...
```

This isolates the advisor entirely from `SessionService._write_lock` (which guards capture/transcribe writes). Advisor reads + capture writes can interleave freely because they use different sessions.

### TacticalAdvisor signature: pure function, no session held

```python
class TacticalAdvisor(Protocol):
    async def advise(
        self,
        meeting_id: str,
        recent_chunks: list[TranscriptChunk],
        playbook: Playbook,
        me_display_name: str,
        counterparty_display_name: str,
        user_question: str | None,
        locale: Literal["zh-TW", "en"],
    ) -> AsyncIterator[str]:
        ...
```

The concrete `VertexFlashAdvisor` constructor takes `vertex_client` + `model_id` only. Caller (sessions/router) is responsible for fetching `recent_chunks` and `playbook` (with its own session). This shape mirrors the slice-5 `PlaybookGenerator` pattern: the module is purely a wrapper around the LLM call, not a DB-aware service.

## Implementation Contract

### Behavior — observable end-state

1. With a meeting in `in_progress` and the user on the detail page, clicking the AdvisorPane's `Get Advice` button SHALL trigger a WS `request_advice` frame within 100 ms; the button becomes disabled within the same render.
2. The user SHALL see a streaming card appear in the AdvisorPane within ~1 second of the click (frontend optimistic render), and the first `advice_chunk` SHALL arrive within ~5 seconds typical / ~10 seconds worst-case acceptable.
3. As `advice_chunk` frames arrive, the latest card's body SHALL update token-by-token; the pane SHALL scroll to keep the latest visible.
4. On `advice_done`, the streaming indicator clears and the `Get Advice` button re-enables.
5. On `advisor_failed`, the card shows the localised error message + a `重試 / Retry` button; clicking retry sends a new `request_advice` (new requestId).
6. Editing the PlaybookPane during a session SHALL persist via the existing PUT endpoint without affecting the live advice stream; the next advice request SHALL see the saved version.
7. Clicking `End Meeting` while an advice request is in-flight SHALL cancel the advice task on the backend and not produce any further `advice_chunk` frames; the partial card shown stays as-is on screen until the meeting reload happens.
8. On client disconnect (page navigation / refresh) mid-stream, the backend SHALL cancel the advice task within 1 second.

### Interface / data shape

WS message contract additions:

| `type` | Direction | Required keys |
| --- | --- | --- |
| `request_advice` | client → server | `type`, `request_id`, `locale`; optional: `user_question` (Slice 9) |
| `advice_chunk` | server → client | `type`, `request_id`, `token` |
| `advice_done` | server → client | `type`, `request_id` |
| `advisor_failed` | server → client | `type`, `request_id`, `error_code`, `message` |

Pydantic models go in `packages/backend/meeting_playbook/sessions/messages.py`; mirror TS types in `packages/web/src/lib/session-ws.ts`.

`SessionRepository.list_chunks_last_60s(meeting_id: str) -> list[TranscriptChunk]` — new method returning rows ordered by `started_at` ascending where `started_at >= now() - INTERVAL '60 seconds'`.

`PlaybookRepository.get_for_meeting(meeting_id: str) -> Playbook | None` — confirm exists; if not, add. Returns the row including all 7 content fields.

`TacticalAdvisor` Protocol (see Decisions section for signature). Concrete `VertexFlashAdvisor` reads the model id from `Settings.vertex_flash_model_id` (default `gemini-2.0-flash-001`).

`get_session_factory_dependency() -> async_sessionmaker[AsyncSession]` — new FastAPI dependency in `packages/backend/meeting_playbook/meetings/dependencies.py`.

`get_tactical_advisor_dependency() -> TacticalAdvisor` — new FastAPI dependency in `packages/backend/meeting_playbook/advisor/dependencies.py`. Returns a process-scoped singleton (LRU cached) instance of `VertexFlashAdvisor`.

Frontend `useMeetingSession` reducer state extension:

```ts
type SessionState = (existing) & {
  advisor: { requests: AdviceRequest[] };
};
```

Reducer actions: `ADVICE_REQUESTED`, `ADVICE_TOKEN`, `ADVICE_DONE`, `ADVICE_FAILED`. Hook exposes `requestAdvice(): void` callback that creates a `request_id` (crypto.randomUUID) and sends the WS frame.

`<AdvisorPane meetingId={id} session={result} />` consumes the hook's `state.advisor` slice + exposes `Get Advice` button.

Env var: `VERTEX_FLASH_MODEL_ID` optional, default `gemini-2.0-flash-001`.

### Failure modes

- **Vertex returns nothing**: `advice_chunk` count is 0; backend still sends `advice_done`; frontend renders an empty card body. Acceptable but worth flagging — the system_instruction's "say so honestly" rule should make this rare.
- **Vertex times out**: `asyncio.timeout(15)` triggers; `advisor_failed { error_code: "advisor.timeout" }`; user can retry.
- **Vertex 429 quota / 401 auth**: typed frame as in error table; user-actionable.
- **Generic exception**: `advisor.unknown` with the raw exception message in `message`.
- **WS closed mid-stream by server (end_meeting)**: advice task receives `CancelledError`, swallows silently, returns. The card on the frontend stays in `streaming` state forever — but the meeting is over and the user is leaving the page; acceptable.
- **WS closed mid-stream by client (browser refresh)**: same as above from backend POV.
- **Two `request_advice` frames arrive before the first one finishes**: frontend should not allow this (button disabled), but defensive backend cancels the prior task. This safeguard exists for Slice 9 chatbox where it is needed.
- **Empty playbook AND empty transcript**: prompt says `(無對話內容) (尚未填寫)`; system_instruction's "say so honestly" rule kicks in; advisor returns a recover-prompting suggestion.
- **PlaybookPane PUT during streaming**: works — different AsyncSession, no contention. The next advice request picks up the saved version.

### Acceptance criteria

Per-decision verification target:

- Streaming protocol: `tests/sessions/test_router_advice.py::test_request_advice_streams_chunks_then_done` — mock TacticalAdvisor that yields 3 strings + finally `advice_done`; assert WS receives 3 `advice_chunk` frames in order then 1 `advice_done`.
- Context window: `tests/sessions/test_repository.py::test_list_chunks_last_60s_excludes_older` — seed 5 chunks at `now() - 30s, 50s, 70s, 90s, 120s`; assert returned 2 (the first two only).
- Speakers in dialogue: `tests/advisor/test_prompts.py::test_user_message_uses_display_names` — feed 2 `me` chunks + 2 `counterparty` chunks; assert prompt contains both display names; assert order is by `started_at`.
- Non-empty playbook fields: `tests/advisor/test_prompts.py::test_user_message_omits_empty_playbook_fields` — playbook with `objective` set + others empty; assert prompt contains `## 目標` + value, does NOT contain `## 對方輪廓` etc.
- Empty playbook + empty transcript: `tests/advisor/test_prompts.py::test_empty_inputs_render_placeholders` — assert `(無對話內容)` + `(尚未填寫)` strings appear.
- Locale switch: `tests/advisor/test_prompts.py::test_locale_switches_system_instruction` — call with `locale="en"`; assert `system_instruction` contains "Reply in English"; with `locale="zh-TW"` assert "請用繁體中文". 
- Vertex streaming wrapper: `tests/advisor/test_vertex_advisor.py::test_advise_yields_text_per_sdk_chunk` — mock SDK's `generate_content_stream` to yield 3 chunks; assert `advise()` yields 3 strings.
- Timeout: `tests/advisor/test_vertex_advisor.py::test_advise_raises_timeout_after_15s` — mock SDK to sleep 20s; assert `asyncio.TimeoutError` raised.
- WS error frame mapping: `tests/sessions/test_router_advice.py::test_vertex_quota_error_emits_advisor_failed` — mock advisor to raise `ResourceExhausted`; assert WS receives `advisor_failed { error_code: "advisor.quota" }` and connection STAYS OPEN.
- Cancel on end_meeting: `tests/sessions/test_router_advice.py::test_end_meeting_cancels_in_flight_advice` — start advice, send `end_meeting` immediately; assert advice task cancelled within 1s, no further `advice_chunk` frames.
- Concurrency / no session contention: `tests/sessions/test_router_advice.py::test_advice_during_active_capture` — start session with active capture writes, send `request_advice`; assert NO `InvalidRequestError` from SQLAlchemy (advisor uses its own session).
- AdvisorPane chat-style append: `packages/web/src/components/advisor-pane.test.tsx::test_two_consecutive_advices_render_two_cards_oldest_first`.
- AdvisorPane streaming render: `advisor-pane.test.tsx::test_advice_chunk_appends_to_active_card_body`.
- AdvisorPane error + retry: `advisor-pane.test.tsx::test_advisor_failed_renders_retry_button` + `test_retry_click_sends_new_request_advice_with_new_request_id`.
- Button disabled while streaming: `advisor-pane.test.tsx::test_get_advice_button_disabled_while_streaming`.
- AdvisorPane hidden when not in_progress: `advisor-pane.test.tsx::test_pane_shows_empty_state_when_session_idle`.
- Detail page wires AdvisorPane: `routes/meetings/detail.test.tsx::test_advisor_pane_renders_when_in_progress`.
- session-ws parses 4 new frames: `lib/session-ws.test.ts::test_parses_advice_chunk_done_failed_request_advice`.
- useMeetingSession reducer: `hooks/use-meeting-session.test.tsx::test_advice_lifecycle_streaming_done` + `test_advice_failed_records_error`.
- locales drift: `locales.test.ts` (existing) — adding new keys to BOTH zh-TW + en files; deep-equal continues to pass.
- Manual smoke (Sean): start a real meeting with mic + BlackHole, click `Get Advice`; first chunk arrives within ~5s; multiple clicks accumulate cards; trigger an error (e.g., disable internet); retry button works.

### Scope boundaries

**In scope:**
- All decisions listed in the Decisions section
- New `tactical-advisor` capability spec
- WS contract additions (4 frames)
- AdvisorPane real implementation (replacing placeholder)
- Backend `TacticalAdvisor` module + Vertex Flash impl + dependencies
- Per-advisor isolated AsyncSession via new `get_session_factory_dependency`
- i18n keys + agent doc

**Out of scope:**
- Chatbox follow-up (Slice 9)
- Auto-trigger advice every N seconds (rejected)
- Persisting advice cards across reload
- Session-history page that shows past advice
- Per-meeting on/off toggle for advisor
- Switching to a different LLM provider (Vertex is the only one per ADR-0006)
- Caching identical recent-question responses
- Advisor "memory" across meetings
- post-meeting summary (Slice 10)
- ASR provider switch (Slice 12, replaces VibeVoice plan per ADR-0028)

## Risks / Trade-offs

- [Vertex Flash 5s+ latency on cold path] → first advice click in a fresh process pays SDK warmup; subsequent clicks faster. Mitigation: nothing in slice; acceptable for personal tool. If it becomes a real issue, pre-warm the Vertex client in app startup.
- [Last-60s window misses important early-meeting context] → ADR-0018 explicitly accepts this. Mitigation: user can manually copy old transcript into the playbook free-form area before clicking advice (clunky but works). Slice 10 summary picks up the rest.
- [User edits playbook without saving, then clicks Get Advice expecting new context] → LLM sees the saved DB version; user is confused. Mitigation: documented behaviour; UI does NOT add a hint per Q6 decision (keep CTA chrome minimal). Revisit if Sean reports the confusion.
- [`advisor_failed` flooding the pane if Vertex is repeatedly down] → user sees error cards stacking. Mitigation: button stays disabled briefly after a failure (~3s) so they can't spam-retry. Add this as a UX polish in apply.
- [In-flight advice card stays in `streaming` state forever after end_meeting] → cosmetic; meeting is closing. Acceptable.
- [Two parallel `request_advice` frames somehow arrive] → defensive backend cancels prior task; frontend invariant should prevent it. Tests cover the defensive path.
- [Vertex billing surprise from spammy Get Advice clicks] → button disabled while streaming + meeting is short → bounded cost. Hard to spam meaningfully. Acceptable for personal use.
