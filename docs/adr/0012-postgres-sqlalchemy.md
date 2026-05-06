# ADR-0012: PostgreSQL with SQLAlchemy 2.0 async + Alembic

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The user already has PostgreSQL installed via Homebrew. The schema needs to support meetings, transcripts, playbooks, recordings, and (via Better Auth — ADR-0021) users / sessions / accounts. Future deploy needs the same DB engine to avoid double migrations.

## Decision
- Database: PostgreSQL (the user's local Homebrew instance for dev; the same engine will be used in any future deploy).
- Backend ORM: SQLAlchemy 2.0 async (mature async support, typed mappings).
- Migrations: Alembic.
- Database name: `meeting_playbook`.
- pgvector extension: **not** installed in v1 — no current RAG / embedding use case (revisit if cross-meeting search is added).

The auth side (Better Auth) writes to the same database but manages its own schema (ADR-0025). Application tables can FK to `user.id` from Better Auth's `user` table.

## Consequences
- Single PostgreSQL instance, two schema authorities (Better Auth + Alembic). The boundary is documented in ADR-0025; new app tables go through Alembic, never Better Auth's CLI.
- SQLite was rejected — the user prefers Postgres and avoids the migration cost later.
- No NoSQL piece. Audio files live on disk under `~/MeetingPlaybook/recordings/`, not in the DB.

## Alternatives considered
- **SQLite** — simplest, but the user explicitly chose Postgres.
- **A separate Postgres instance for auth** — overkill for one user.
