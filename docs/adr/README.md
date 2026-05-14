# Architecture Decision Records

Each file records one decision with its context, consequences, and alternatives.

Format inspired by Michael Nygard's ADR template, kept short.

## Index
1. [Personal side project, local-first](./0001-personal-side-project.md)
2. [MVP includes pre, in, and post-meeting](./0002-mvp-three-phases.md)
3. [macOS-only target](./0003-macos-only.md)
4. [BlackHole for dual-channel audio capture](./0004-blackhole-audio-capture.md)
5. [Switchable ASR providers (Whisper + VibeVoice-ASR)](./0005-switchable-asr-providers.md)
6. [Vertex AI as LLM provider](./0006-vertex-ai-llm.md)
7. [Python backend (FastAPI + uv + ruff)](./0007-python-backend-fastapi.md)
8. [TypeScript frontend (React + Vite + Bun + shadcn)](./0008-typescript-frontend.md)
9. [oxlint + oxfmt for TS lint and format](./0009-oxlint-oxfmt.md)
10. [bun test for TypeScript testing](./0010-bun-test.md)
11. [pytest for Python testing](./0011-pytest.md)
12. [PostgreSQL with SQLAlchemy 2.0 async + Alembic](./0012-postgres-sqlalchemy.md)
13. [Bun workspaces monorepo + concurrently](./0013-bun-workspaces-monorepo.md)
14. [WebSocket for backend-frontend realtime](./0014-websocket-realtime.md)
15. [Google Calendar as the only pre-meeting data source](./0015-google-calendar-only.md)
16. [Binary speaker labels with custom display names](./0016-binary-speaker-labels.md)
17. [Hybrid trigger for in-meeting advice (button + chatbox)](./0017-hybrid-advice-trigger.md)
18. [LLM context: last 60s transcript + full playbook](./0018-llm-context-window.md)
19. [Hybrid playbook structure (free-form + structured fields)](./0019-hybrid-playbook-structure.md)
20. [30-day recording retention auto-cleanup](./0020-recording-retention.md)
21. [Better Auth + Google OAuth + TOTP 2FA](./0021-better-auth.md)
22. [i18n with zh-TW (default) + en](./0022-i18n-zh-en.md)
23. [structlog (Python) + console (TS) for logging](./0023-logging.md)
24. [lefthook pre-commit hooks](./0024-lefthook-pre-commit.md)
25. [No TS ORM; Better Auth uses pg.Pool directly](./0025-no-ts-orm.md)
27. [Calendar scope linked to meeting create](./0027-calendar-scope-link.md)
28. [Qwen3-ASR replaces VibeVoice](./0028-qwen3-asr-replaces-vibevoice.md)
29. [Hybrid speaker attribution (amends ADR-0016)](./0029-hybrid-speaker-attribution.md)
