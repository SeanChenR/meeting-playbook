# ADR-0018: LLM context for the tactical advisor — last 60s transcript + full playbook

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
What does the advisor model see when the user clicks "Get Advice"? Three options:
1. Last 60s transcript + full playbook (cheap, fast).
2. Full meeting transcript so far + full playbook (richer, slower, more tokens).
3. Rolling LLM-generated summary every 5 min + last 60s + playbook (smart but adds a background job).

## Decision
Use option 1: the last 60 seconds of transcript (both speakers) + the full playbook (free-form markdown + structured fields).

For the chatbox, prior chatbox messages in the current meeting are also included.

## Consequences
- Latency stays low (fewer tokens to Gemini Flash).
- Costs stay predictable.
- Long meetings (>30 min) lose deep context; this is acceptable for v1 because the playbook is the canonical source of "what we want to do".
- Option 3 (rolling summary) becomes a v2 optimization if the user feels missing context.

## Alternatives considered
- **Full transcript** — slow and expensive past 30-minute meetings.
- **Rolling summary** — adds a background pipeline; defer.
