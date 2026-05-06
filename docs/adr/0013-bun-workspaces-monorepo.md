# ADR-0013: Bun workspaces monorepo with concurrently

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Three packages (`web`, `auth`, `backend`) need to live together for shared lifecycle and a single `bun run dev` to start them all. The user explicitly asked for a monorepo with concurrent startup.

## Decision
- Monorepo via Bun workspaces (`packages/*`).
- `concurrently` runs `vite` (web), `bun --watch` (auth), and `uv run fastapi dev` (backend) under a single root `bun run dev` command.
- Each package owns its own `package.json` (or `pyproject.toml`) and runs its own scripts.
- The root `package.json` only orchestrates and holds dev tooling shared across packages.

## Consequences
- One command to spin up the whole stack.
- Per-package CI / linting is straightforward: `bun --filter '<name>' <script>`.
- The Python backend is not technically a Bun workspace — it sits in `packages/backend/` for filesystem cohesion but is invoked via `uv` from the root.

## Alternatives considered
- **Separate repos** — too much overhead for one user.
- **pnpm / Yarn workspaces** — Bun is the preferred TS runtime per the user's stack; mixing package managers adds friction.
- **Turborepo / Nx** — premature for three packages without shared TS code.
