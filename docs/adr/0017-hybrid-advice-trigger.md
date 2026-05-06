# ADR-0017: Hybrid trigger for the in-meeting tactical advisor — button + chatbox

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The reference article uses a single "Get Advice" button. Auto-suggestions every 30s would be intrusive. A pure chatbox is flexible but slow. The user wants both speed (single click) and depth (follow-up questions).

## Decision
The right column has both:
- A prominent **"Get Advice"** button — one click, a single-shot suggestion based on the last 60s of transcript + the full playbook (ADR-0018). Latency target: 3-5s.
- A **chatbox** — the user types a question (e.g., "他剛說的 budget 怎麼回？"), Gemini answers with the same context plus prior chatbox history.

Both share the same backend prompt scaffolding; the difference is whether the user supplies an explicit question.

## Consequences
- The advisor module needs two entry points but one underlying `advise()` function.
- Chatbox history is per-meeting; not persisted across meetings.
- No auto-trigger in v1; revisit if the user finds themselves spamming the button.

## Alternatives considered
- **Button only** — too rigid for follow-ups.
- **Chatbox only** — too slow for "give me something now".
- **Auto-suggest every N seconds** — too noisy; can be added later.
