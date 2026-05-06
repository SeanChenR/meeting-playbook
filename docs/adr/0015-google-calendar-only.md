# ADR-0015: Google Calendar as the only pre-meeting data source

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Pre-meeting playbook generation can pull from Calendar, Email, project trackers (Notion, Linear), CRM, etc. Each integration adds OAuth + API + heuristics for "find relevant content for this meeting".

## Decision
Integrate **only** Google Calendar in v1. The user grants OAuth access (separate from the Better Auth login OAuth — different scope set). For each upcoming meeting, the backend pulls title, attendees, time, description, and uses Gemini 2.5 Pro to draft a playbook.

The user manually edits the playbook fields; this is the expected workflow, not a v1 limitation.

## Consequences
- One OAuth integration to maintain.
- The playbook draft will be sparse for meetings where the Calendar event is sparse — that is the user's signal to add context manually.
- Gmail / Notion / Linear / Slack stay out of v1 scope.

## Alternatives considered
- **Calendar + Gmail** — Gmail thread relevance heuristics are non-trivial; postpone until the user feels the lack.
- **Full integration suite** — premature complexity.
- **No integration (manual only)** — recommended initially, declined by the user as part of "三段全做".
