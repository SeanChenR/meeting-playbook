# ADR-0019: Hybrid playbook structure — free-form markdown + structured field metadata

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
A free-form markdown playbook is flexible but hard for the LLM to use precisely (no anchor points). A pure structured schema (objective, anticipated objections, etc.) is great for the LLM but rigid for the user.

## Decision
Hybrid:
- **Primary visual**: a free-form markdown editor where the user writes the playbook naturally.
- **Structured fields** (separate columns / DB fields): objective, counterparty profile, anticipated topics, anticipated objections, talking points, red lines.
- The user can fill structured fields directly, or write free-form and let Gemini 2.5 Pro extract / suggest values into the structured fields.
- The frontend offers a toggle: "free-form view" vs "structured view".

## Consequences
- Schema stores both. The free-form text is the source of truth; structured fields are derived metadata that may be edited too (last-write-wins).
- The advisor model gets both — structured fields are the primary signal ("this is the user's anticipated objection X — counterparty just raised something close"), free-form is the supporting context.
- Pre-meeting Calendar-driven playbook generation (ADR-0015) populates the structured fields from event metadata as a starting point.

## Alternatives considered
- **Free-form only** — LLM has weaker grounding.
- **Structured only** — too rigid for a creative prep doc.
