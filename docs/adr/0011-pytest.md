# ADR-0011: pytest for Python testing

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
pytest is the de facto Python test framework with strong async support (`pytest-asyncio` or built-in fixtures), parametrization, and an enormous plugin ecosystem.

## Decision
Use `pytest` for all Python tests in `packages/backend/tests/`. Configure `asyncio_mode = "auto"` so async tests don't need an explicit decorator.

## Consequences
- Standard tooling, easy to onboard.
- Async FastAPI / SQLAlchemy code gets first-class test support.
- Coverage measurement uses `pytest-cov` (added when first tests are written).

## Alternatives considered
- **unittest** — verbose, weaker async story.
- **nose2** — no compelling advantage.
