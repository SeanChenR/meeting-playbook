# ADR-0002: MVP includes pre-, in-, and post-meeting phases

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The reference article (yu-wenhao.com) describes a three-phase product (pre/in/post). The author considered scoping to in-meeting only as the highest-value differentiator; the user chose to do all three.

## Decision
Implement all three phases in the MVP:
- **Pre-meeting** — Google Calendar integration generates a playbook draft.
- **In-meeting** — dual-channel audio capture, ASR, live transcript, tactical advisor.
- **Post-meeting** — markdown summary with decisions and action items.

## Consequences
- More upfront work, especially for the Google Calendar OAuth integration (ADR-0015).
- Vertical-slice issue breakdown should still let the in-meeting slice land first; pre- and post- can layer in.
- Single coherent product story, matching the reference article.

## Alternatives considered
- **In-meeting only MVP** — recommended initially, declined by the user as "三段全做，花不了多少時間".
- **Post-meeting only** — too small to be interesting and overlaps with existing summarizer tools.
