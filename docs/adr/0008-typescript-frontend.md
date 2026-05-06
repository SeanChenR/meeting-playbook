# ADR-0008: TypeScript frontend — React + Vite + Bun + shadcn/ui + Tailwind

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The frontend is a three-pane single-page app: playbook (left), live transcript (middle), tactical advisor (right). It needs WebSocket streaming, a markdown editor for the playbook, and a chat-style component for the advisor. This matches the user's default web stack.

## Decision
- Language: TypeScript
- Runtime: Bun
- Bundler / dev server: Vite
- UI framework: React
- Component library: shadcn/ui
- Styling: Tailwind CSS
- i18n: react-i18next (ADR-0022)
- Test runner: `bun test` (ADR-0010)
- Lint + format: oxlint + oxfmt (ADR-0009)

## Consequences
- Standard, well-documented stack — most onboarding friction is project-specific, not stack-specific.
- shadcn/ui copies components into the repo (rather than imports), which keeps the dependency surface small and customization easy.
- Vite dev server (port 5173) is one of three dev processes (alongside Bun.serve auth and FastAPI backend); the root `bun run dev` script spawns all three via `concurrently`.

## Alternatives considered
- **Streamlit / Gradio (all Python)** — faster to scaffold but produces a "tool that looks like a tool", not a polished UI. The three-pane interaction needed here is awkward to express.
- **Next.js** — SSR is unnecessary for a localhost personal tool; pure SPA via Vite is lighter.
