# ADR-0010: bun test as the TypeScript test runner

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Bun ships a built-in test runner with a Jest/Vitest-compatible API. Adding Vitest separately would duplicate runtime overhead and config.

## Decision
Use `bun test` for all TypeScript tests in `packages/web` and `packages/auth`.

## Consequences
- Zero additional dependencies for testing.
- Tests run via the same Bun runtime as the dev/build pipeline — fewer "works in test, fails at runtime" surprises.
- Limited compatibility with niche Vitest plugins; acceptable given the project scope.

## Alternatives considered
- **Vitest** — extra dependency for no win on this stack.
- **Jest** — slower, heavier, dated.
