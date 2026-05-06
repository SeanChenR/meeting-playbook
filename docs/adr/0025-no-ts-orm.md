# ADR-0025: No TS ORM — Better Auth uses pg.Pool directly

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The auth package needs database access only for Better Auth's user / session / account / verification tables. The backend already owns SQLAlchemy + Alembic for the application schema (ADR-0012). Bringing Drizzle / Prisma / Kysely into `packages/auth` purely for Better Auth would be a heavy dependency for a small surface.

## Decision
- The auth package depends on `pg` (the node-postgres library) directly.
- A `pg.Pool` instance is constructed from the same `DATABASE_URL` the backend uses.
- Better Auth is configured with `database: <pg.Pool instance>`; it manages its own table schema via its CLI (`better-auth migrate` or equivalent).
- Application tables in the same database are managed by Alembic and live entirely on the backend side.
- Cross-side FK: application tables reference Better Auth's `user.id`. We document this contract; we do not codegen it.

## Consequences
- One PostgreSQL database, two migration tools (Better Auth CLI for auth tables, Alembic for everything else).
- Onboarding sequence: run Better Auth migration first (creates `user` table), then Alembic (creates app tables that FK to it).
- No TS ORM in the codebase — `packages/web` does not touch the DB at all (frontend goes through HTTP).
- If a future need arises for app-side queries from TS, this ADR gets revisited.

## Alternatives considered
- **Drizzle / Prisma / Kysely in the auth package** — adds an ORM dependency for one library's internal needs.
- **Move all DB access to the backend (no DB in `packages/auth`)** — would require Better Auth to call out to the backend for storage, fighting Better Auth's own integration design.
