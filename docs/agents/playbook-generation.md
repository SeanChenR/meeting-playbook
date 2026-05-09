# PlaybookGenerator — agent notes

> Slice 5 (`slice-05-calendar-llm-playbook`) outcome.
> Spec: `openspec/specs/playbook-generation/spec.md` (after archive).
> Module: `packages/backend/meeting_playbook/playbook_generation/`.

## What it does

`PlaybookGenerator.generate(event: CalendarEvent) -> PlaybookDraft`:
turns a Google Calendar event record into a 7-field playbook draft
suitable for direct upsert via `PlaybookRepository.upsert_for_meeting`.

The output shape is identical to `PlaybookUpsertPayload`:

- `free_form_markdown` (≥ 3 non-blank lines)
- `objective` (non-empty after trim)
- `counterparty_profile`
- `anticipated_topics`
- `anticipated_objections`
- `talking_points`
- `red_lines`

## Vertex-only invariant

This module **MUST NOT** import or call any non-Vertex AI provider —
no Anthropic, no OpenAI, no Cohere, no Mistral. The official
`google-genai` SDK (Vertex AI mode) is the only allowed path. There is
a unit test that greps the source to enforce this.

Authentication flows through Application Default Credentials
(`GOOGLE_APPLICATION_CREDENTIALS` env var pointing at a service account
JSON with the `Vertex AI User` role).

## Two-stage prompt strategy

The generator runs up to **two** LLM calls per event:

1. **Primary prompt** — full event metadata (title, attendees, time,
   description, organizer). The prompt explicitly tells the model to use
   general best practices for sparse events instead of leaving fields
   empty.

2. **Fallback prompt** — invoked only if the primary response leaves
   any of the seven fields empty (or `free_form_markdown` < 3 non-blank
   lines). The fallback names the missing fields explicitly and asks the
   model to re-derive them from the event title plus general best
   practices.

If a field is **still** empty after both calls, the generator inserts a
localized sentinel string (`「（請自行填寫 / Please fill in）」`) so the
playbook editor never displays an empty-looking field.

Vertex's structured-output mode (`response_mime_type: application/json`
+ a `response_schema` of seven required string keys) provides a strong
guarantee against the primary call returning an entirely malformed
response — but `_parse_draft` still validates each field's type defensively.

## Failure-code mapping

The router translates generator exceptions into the standard error
envelope:

- `PlaybookGenerationTimeout` (60-second deadline exceeded) → HTTP 504
  + `playbook.generation_timeout`
- `PlaybookGenerationFailed` (JSON parse / schema-mismatch) → HTTP 502
  + `playbook.generation_failed`

The 60-second timeout is configurable per instance for tests via
`PlaybookGenerator(timeout_seconds=...)` but production keeps the spec
default.

## Repository round-trip

`generate(event)` returns a `PlaybookDraft` whose keys are exactly the
seven content fields defined by `playbook-management`. Callers are
expected to pass the draft straight to `PlaybookRepository.upsert_for_meeting`
without any transformation. There is an integration test that exercises
this round trip end-to-end.

## Sample fixtures

`packages/backend/tests/playbook_generation/fixtures/` carries six
representative Calendar event JSON files: `rich.json`, `sparse.json`,
`long.json`, `zh.json`, `en.json`, `mixed.json`. Each must produce
seven non-empty fields under the parametrized test
`test_generator_produces_seven_non_empty_fields`. New event shapes that
break should be added as new fixtures here, never removed.

## Viewer perspective (slice-05 ingest round 2)

The generator does not write a third-person summary of the meeting — it
writes preparation **for the signed-in viewer**, framed by the viewer's
role in the meeting. The router passes `viewer_email` and `viewer_name`
(from the gateway-injected `X-User-Email` / `X-User-Name` headers) into
`PlaybookGenerator.generate(event, *, viewer_email, viewer_name)`, which
classifies the viewer into one of three roles:

- `organizer` — viewer's email matches `event.organizer_email`
  (case-insensitive, whitespace-trimmed). Prompt instructs the model that
  the viewer is hosting / driving the meeting.
- `attendee` — viewer's email matches an attendee email AND is not the
  organizer. Prompt instructs the model that the viewer was invited and
  the playbook should read as participant preparation.
- `external` — viewer's email matches neither. Prompt instructs the model
  that the viewer is previewing the event from a subscribed calendar
  (the typical case is class / community / shared-calendar events).

Empty `viewer_email` is allowed and degrades safely to `external`. Empty
`viewer_name` falls back to the email's local-part, then finally to the
literal "the user" if both are empty.

Both `build_primary_prompt` and `build_fallback_prompt` prepend a leading
paragraph (rendered by the private `_render_viewer_block`) that names the
viewer + email + role + role-specific guidance + others list, then asks
the model to write the playbook from the viewer's point of view. The
seven-field output schema is unchanged across roles — only the textual
content varies.

Role classification lives in
`meeting_playbook.calendar.identity.classify_viewer_role`. Tests for
that pure function are in
`packages/backend/tests/calendar/test_classify_viewer_role.py`.
