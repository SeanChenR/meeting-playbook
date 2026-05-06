# ADR-0024: lefthook for pre-commit hooks

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The repo has both Python (ruff) and TypeScript (oxlint, oxfmt) tooling. A unified pre-commit framework that can run both is preferable to language-specific solutions.

## Decision
Use `lefthook` (Go binary, fast, simple YAML config). One `lefthook.yml` at the repo root with parallel pre-commit commands:
- `ruff check` and `ruff format --check` on staged Python files.
- `oxlint` and `oxfmt --check` on staged TS/JS files.

## Consequences
- Pre-commit runs in seconds (Rust-based linters, Go-based runner).
- One config to maintain across both languages.
- `lefthook install` is part of project onboarding; documented in README.

## Alternatives considered
- **pre-commit (Python tool)** — fine but adds a Python dependency for a project-wide concern.
- **husky + lint-staged** — slower and TS-centric; awkward for the Python side.
