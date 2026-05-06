# ADR-0001: Personal side project, local-first, future-deploy-friendly

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The user wants an AI meeting assistant. Existing SaaS tools cost $10-30/month and store recordings on third-party clouds. The user has a clear personal need; deploying it to others is a possible future, not the current goal.

## Decision
Build as a single-user, local-first tool. Optimize for "Sean uses this on his M3 Pro tonight" first, "could be deployed later" second. Do not over-invest in multi-tenancy, sharing, or distribution today, but do not architect choices that would block them.

## Consequences
- All persistence is local PostgreSQL.
- Auth (ADR-0021) is included from day one as a small future-proofing investment.
- BlackHole onboarding pain (ADR-0004) is acceptable because it is one-time for the single user.
- No CI / cloud infrastructure / billing scaffolding for now.

## Alternatives considered
- **Pure SaaS subscription** — defeats the privacy and customization goals.
- **Multi-tenant from day one** — premature complexity for one user.
