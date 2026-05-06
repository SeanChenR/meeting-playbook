# ADR-0009: oxlint + oxfmt for TypeScript lint and format

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Modern TypeScript linters and formatters built in Rust (oxc family) are dramatically faster than ESLint + Prettier and on par with Biome.

## Decision
Use `oxlint` (lint) and `oxfmt` (format) for all TypeScript / JavaScript files in `packages/web` and `packages/auth`. No ESLint, no Prettier, no Biome.

## Consequences
- Fast pre-commit hooks (ADR-0024).
- One less config file to maintain (no ESLint config + Prettier config combo).
- The TS ecosystem's plugin coverage in oxlint is younger than ESLint's; rare custom rules may not be available, accepted as a trade-off.

## Alternatives considered
- **ESLint + Prettier** — slower and noisier configs.
- **Biome** — comparable choice; oxlint preferred for the user's existing familiarity.
