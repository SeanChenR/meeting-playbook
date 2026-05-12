# ui-design-system Specification

## Purpose

Defines the project-wide design token catalogue (colors, spacing, typography)
and the variant standards for the shared shadcn-derived components in
`packages/web/src/components/ui/` (Card, Button, Alert). The token set lives
in `packages/web/src/index.css` and every route + component consumes it via
Tailwind utility classes referencing CSS custom properties (e.g.
`bg-(--color-primary)`); hard-coded hex values, RGB literals, and arbitrary
spacing values in component class strings are design-system violations.

Scope today (slice-7): the design system is largely the result of slice-7
round 2's housekeeping. That round added the `warning` variant to `Alert`
and the equal-height column constraint shared with `meeting-detail-layout`,
and re-stated the existing Button / Card / locale-mirror discipline so the
catalogue is enforceable. The broader visual overhaul (richer color palette,
microinteractions, MagicUI integration, removing remaining inline styling)
is out of scope here and deferred to slice-08-ui-overhaul; future agents
working in this area should treat slice-7's enforcement as the floor, not
the ceiling.

## Requirements

### Requirement: The web app uses a single coherent design token set

The web app SHALL define a single design token set in `packages/web/src/index.css` that every route + component consumes via Tailwind utility classes referencing CSS custom properties (e.g. `bg-(--color-primary)`, `text-(--color-foreground)`, `gap-(--spacing-md)`). Token categories required:

- **Color tokens**: at minimum `--color-background`, `--color-foreground`, `--color-card`, `--color-card-foreground`, `--color-primary`, `--color-primary-foreground`, `--color-secondary`, `--color-secondary-foreground`, `--color-muted`, `--color-muted-foreground`, `--color-border`, `--color-input`, `--color-ring`, `--color-destructive`, `--color-destructive-foreground`, plus a 6-step neutral grey scale.
- **Spacing scale**: 8 step scale (e.g. `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`px) — Tailwind's default `1` through `16` mapped to these values. Arbitrary values (`mt-[7px]`, `p-[13px]`) SHALL NOT appear in the codebase.
- **Typography pairing**: one sans-serif family for UI (`Inter` or comparable) and one mono family (`Geist Mono` or comparable). Size scale limited to `xs / sm / base / lg / xl / 2xl` Tailwind tokens.

Hard-coded color hex values, RGB literals, or arbitrary spacing values in component class strings SHALL be considered design-system violations and SHALL be replaced with token references.

#### Scenario: All visible components consume color tokens

- **GIVEN** every route page (`login`, `signup`, `home`, `meetings/list`, `meetings/new`, `meetings/$id`, `meetings/calendar`, `calendar/import`, `totp/enroll`, `totp/verify`)
- **WHEN** a reviewer greps the rendered className strings for hex literals (`#[0-9a-fA-F]{3,8}`) or `rgb(`/`rgba(` calls outside of `index.css`
- **THEN** zero matches SHALL be returned (all colour expressed through `--color-*` tokens)

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Card, Button, and Alert components have a fixed variant catalog

The shared shadcn-derived components in `packages/web/src/components/ui/` SHALL expose a fixed catalogue of variants used app-wide:

- **Button**: exactly four variants — `primary` (default), `outline`, `ghost`, `destructive`. All variants SHALL share the same height token (e.g. `h-9`) and consistent horizontal padding. Hover and focus states SHALL be subtle and visually consistent across variants.
- **Card**: a single Card component with subtle border (`border-(--color-border)`), soft shadow (`shadow-sm`), and consistent padding via `CardHeader` / `CardContent` / `CardFooter`. No per-page custom card styling.
- **Alert**: exactly four variants — `destructive`, `warning`, `info`, `success`. Each renders an icon + body; layout consistent across variants.

Pages SHALL use these variants via prop and SHALL NOT override colour or spacing inline. Routes that historically used emoji or arbitrary divs as alerts SHALL migrate to the `Alert` component.

#### Scenario: Buttons across pages share the same height

- **GIVEN** every clickable `<button>` rendered by the app's route pages
- **WHEN** a viewport check inspects their bounding boxes
- **THEN** all primary / outline / ghost / destructive buttons SHALL have the same computed height (within 1px); only `<button data-size="sm">` may differ

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Detail page columns mode renders balanced panes

(Cross-references the `meeting-detail-layout` spec's equal-height requirement.) In columns mode the three panes SHALL share equal visible height via the design system's height-constraint utility (`h-[calc(100vh-220px)]` on the grid container plus `h-full` on each pane wrapper). This requirement is enforced at the design-system layer so future panes added to the same grid inherit the same constraint.

#### Scenario: Equal height in columns mode

- **GIVEN** the detail page in columns mode at viewport >=1024px
- **WHEN** the three pane wrappers render
- **THEN** they SHALL have equal `getBoundingClientRect().height` (within 1px tolerance)

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: All UI strings remain in both locale files (slice-7 round 2 housekeeping)

The deep-equal locale-drift assertion in `packages/web/src/locales/locales.test.ts` SHALL continue to pass after the design system is applied. Any new aria-labels, callouts, helper text, or visible strings introduced by the UI overhaul SHALL appear in both `zh-TW.json` and `en.json`. Component-level Tailwind-only changes (color, spacing, typography) SHALL NOT introduce hard-coded user-facing strings.

#### Scenario: locales.test.ts deep-equal still passes

- **WHEN** `bun test src/locales/locales.test.ts` runs after the slice-7 round-2 design overhaul
- **THEN** the test SHALL pass (zero key drift between zh-TW.json and en.json)

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Design tokens SHALL be expressed as oklch-based CSS variables across two themes

The token catalogue in `packages/web/src/index.css` SHALL declare two complete theme blocks selected via the `data-theme` attribute on `documentElement`:

- `[data-theme="light"]` (default, also applied to bare `:root` so SSR-style flashes default to light) — primary hue centred on violet (`--primary-hue: 280`), surface near-white with subtle violet tint, foreground deep neutral.
- `[data-theme="dark"]` — primary hue centred on warm orange (`--primary-hue-dark: 50`), surface deep neutral with subtle warm tint, foreground near-white.

Every colour token SHALL be expressed in `oklch(...)` with explicit lightness / chroma / hue; raw hex literals SHALL NOT appear in component class strings or token definitions. Spacing, radius, and typography tokens SHALL be expressed as `--space-N`, `--radius-N`, `--text-N` CSS variables consumed by components.

#### Scenario: Light theme is applied on first render without user preference

- **GIVEN** a fresh browser session with no `mp-theme` value in `localStorage` AND `prefers-color-scheme: light`
- **WHEN** the `ThemeProvider` mounts
- **THEN** `documentElement` SHALL gain `data-theme="light"` AND `--color-primary` SHALL resolve to an oklch value with hue near 280

#### Scenario: Dark theme is applied when system prefers dark

- **GIVEN** a fresh browser session with no `mp-theme` value AND `prefers-color-scheme: dark`
- **WHEN** the `ThemeProvider` mounts
- **THEN** `documentElement` SHALL gain `data-theme="dark"` AND `--color-primary` SHALL resolve to an oklch value with hue near 50

#### Scenario: No raw hex colour appears in component class strings

- **GIVEN** the production bundle of `packages/web` after build
- **WHEN** the bundled CSS is scanned for hex colour literals (`#[0-9a-fA-F]{3,8}` patterns) inside component class attributes
- **THEN** the only matches SHALL be inside `index.css` token definitions or inline SVG fill / stroke attributes used by lucide icons; no component-level `className` SHALL contain a raw hex


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: ThemeProvider SHALL persist user choice and expose a typed Context

The web app SHALL provide a `ThemeProvider` React component (in `packages/web/src/lib/theme-provider.tsx`) that wraps `App` and exposes a `useTheme()` hook returning `{ theme, resolved, setTheme }`. `theme` is the raw user preference (`"light" | "dark" | "system"`); `resolved` is the effective theme (`"light" | "dark"`) after collapsing `"system"` against `prefers-color-scheme`. `setTheme` SHALL persist the preference to `localStorage.mp-theme`.

The `theme-toggle` component (in `packages/web/src/components/theme-toggle.tsx`) SHALL render in the `NavBar` right-side cluster and SHALL cycle through `light` → `dark` → `system` on click.

#### Scenario: Toggling theme persists across reload

- **GIVEN** the user is on any `ProtectedShell` route with `data-theme="light"`
- **WHEN** the user clicks the theme toggle until `data-theme="dark"` is applied AND reloads the browser
- **THEN** on reload `localStorage.mp-theme` SHALL equal `"dark"` AND `documentElement` SHALL re-mount with `data-theme="dark"` immediately (no flash of light)

#### Scenario: System preference change updates resolved theme when theme="system"

- **GIVEN** the user has set `theme = "system"` AND the OS is currently `prefers-color-scheme: light`
- **WHEN** the OS preference changes to `dark` while the app is open
- **THEN** `documentElement` `data-theme` SHALL update to `"dark"` without page reload (via `matchMedia('(prefers-color-scheme: dark)').addEventListener`)

#### Scenario: Corrupted localStorage falls back to system

- **GIVEN** `localStorage.mp-theme` holds an invalid value like `"purple"` or random garbage
- **WHEN** `ThemeProvider` mounts
- **THEN** the provider SHALL fall back to `theme = "system"` AND SHALL NOT throw


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: Five shadcn primitives SHALL be added with consistent file layout

The web app SHALL gain the following primitives under `packages/web/src/components/ui/`, each a thin wrapper over the matching radix headless primitive styled with Tailwind v4 utility classes consuming the token CSS variables:

- `select.tsx` — wraps `@radix-ui/react-select`; replaces every native `<select>` in feature components (notably `AsrProviderSelector`).
- `dropdown-menu.tsx` — wraps `@radix-ui/react-dropdown-menu`; used by `theme-toggle` and `locale-toggle`.
- `tooltip.tsx` — wraps `@radix-ui/react-tooltip`; used by `RecordingBadge` dot and `CaptureIndicator` status icons.
- `skeleton.tsx` — pure CSS shimmer (no radix dependency); replaces ad-hoc loading placeholders.
- `sonner.tsx` — wraps `sonner` toast library; mounted once by `ProtectedShell`. Replaces every in-component inline error `<span>` that currently surfaces mutation errors.

Each primitive SHALL be unit-tested with a smoke test asserting at least mount + visible-by-default behaviour. None SHALL use inline `style={{...}}` props for cosmetic styling (lucide icon sizing inline is allowed).

#### Scenario: AsrProviderSelector uses shadcn Select after the overhaul

- **GIVEN** the meeting detail page after this change ships
- **WHEN** the `AsrProviderSelector` is rendered
- **THEN** the DOM SHALL contain a `[role="combobox"]` from radix-select (not a native `<select>` element) AND `data-testid="asr-provider-selector"` SHALL still resolve to the trigger button so the existing component test keeps working

#### Scenario: Mutation errors surface via Sonner toast, not inline span

- **GIVEN** the `RerunButton` POST mutation fails with a `RerunApiError`
- **WHEN** the mutation `onError` handler fires
- **THEN** a toast SHALL appear via `sonner` carrying the localised error message AND no inline `<span class="...destructive...">` SHALL be rendered next to the button


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: TranscriptChunk speaker contrast SHALL exceed the slice-7 baseline

Each rendered transcript chunk in `TranscriptPane` SHALL carry every one of the following visual cues simultaneously (not "any one of"):

1. A 3px solid left border in either `--color-me` (我方) or `--color-them` (對方).
2. A 5-20% tint background in `--color-me-soft` or `--color-them-soft` (mixed via `color-mix(in oklch, ...)` with `--me-tint-alpha` / `--them-tint-alpha` controlling intensity).
3. A speaker dot rendered before the speaker name, filled with the same hue as the left border.
4. The speaker name in semibold (`font-weight: 600`) in `--color-me` or `--color-them`.

`--color-them` SHALL be measurably more saturated than `--color-me` (chroma differential SHALL exceed 0.05 in light theme) so users can scan dialogue ownership at a glance.

#### Scenario: Counterparty chunk carries all four visual cues

- **GIVEN** a transcript chunk with `speaker = "counterparty"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the chunk wrapper SHALL have:
  - `border-left-width: 3px` AND `border-left-color` resolving to `--color-them` AND
  - `background-color` resolving to a non-transparent mix of `--color-them-soft` AND
  - a `[data-testid="speaker-dot"]` element with background `--color-them` rendered before the name AND
  - the speaker name element with `font-weight: 600` and colour `--color-them`

#### Scenario: Me chunk uses the lighter, less saturated variant

- **GIVEN** a transcript chunk with `speaker = "me"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the same four cues SHALL apply but using `--color-me` (lighter, lower chroma) AND `--color-me-soft` (lighter background); the visual hierarchy SHALL clearly place 對方 as the focal point


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: Animation library usage SHALL follow the framer-motion / magicui / animate-ui split

The web app SHALL declare three animation libraries with disjoint responsibilities:

- `framer-motion` SHALL be used for React component-level entry / exit animations: Pane stagger entry, Tabs cross-fade, modal scale + fade, hover micro-interactions on Buttons and Cards.
- `magicui` SHALL be used for self-contained visual effects: shimmer skeleton, NumberTicker on stat cards, optional Particles on auth shells, Marquee on the calendar import list.
- `animate-ui` SHALL be used for route-level transitions: route change opacity overlay, layout transition when the workspace switches between three-column and stacked.

When two libraries provide the same primitive (e.g. both offer a fade animation), `framer-motion` SHALL win. Animation presets SHALL be centralised in `packages/web/src/lib/motion-presets.ts` exporting typed `Variants` and `Transition` objects (paneEnter, paneStagger, tabContent, modalScale, cardHover).

All animations SHALL be disabled when `window.matchMedia('(prefers-reduced-motion: reduce)').matches` returns true; this SHALL be enforced via a shared `useReducedMotion()` hook applied at the preset level (`framer-motion` already supports this hook natively).

#### Scenario: Reduced motion disables all framer-motion animations

- **GIVEN** the user has `prefers-reduced-motion: reduce` set at the OS level
- **WHEN** any animated component (e.g. a Pane entering with `paneEnter` variants) renders
- **THEN** the component SHALL render at its final state immediately with no transition (no opacity fade, no translateY)

#### Scenario: Motion presets are reused across components

- **GIVEN** the codebase after this change ships
- **WHEN** the source is scanned for inline `framer-motion` `Variants` definitions
- **THEN** preset objects (paneEnter, paneStagger, tabContent, modalScale, cardHover) SHALL all be imported from `packages/web/src/lib/motion-presets.ts`; no component SHALL declare an equivalent inline preset

<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: Icon library usage SHALL follow the lucide-react / animate-ui split

The web app SHALL split icon usage between `lucide-react` and the
`@animate-ui/icons-*` registry along the following axis:

- `@animate-ui/icons-*` SHALL be used for user-facing action triggers
  and hero / status glyphs. The curated set is exactly 10 icons
  installed under `packages/web/src/components/animate-ui/icons/`:
  `arrow-left`, `copy`, `download`, `loader`, `lock`, `log-out`,
  `plus`, `refresh-cw`, `sparkles`, `trash`. (The proposal originally
  scoped 15 icons; 5 — `languages`, `mic`, `shield`, `shield-check`,
  `square` — return HTTP 404 from the animate-ui registry as of
  2026-05 and SHALL continue importing from `lucide-react` until the
  registry covers them.)
- `lucide-react` SHALL be used for structural markers inside shadcn
  primitives (Check, Chevron variants), passive layout indicators
  (Columns3, Rows3), theme-state glyphs (Sun, Moon, Monitor),
  Calendar, plus the 5 user-action icons not yet on the animate-ui
  registry (Mic, Square, Shield, ShieldCheck, Languages). Importing
  additional lucide icons NOT in this list for user-action triggers
  SHALL be reviewed as a candidate for animate-ui promotion.

The animate-ui wrapper component (`icon.tsx`) SHALL be the single
file in the web package that imports from `motion/react`. All
individual icon files in `animate-ui/icons/` SHALL re-use the
wrapper rather than rolling their own Motion-React imports.

Animations on swapped icons SHALL trigger on hover by default
(`animateOnHover` prop). Continuous-loop animations (e.g. submit
spinners on the auth forms) SHALL use the per-icon's loop variant
name — `animate="spin"` for `Loader`, `animate="rotate"` for
`RefreshCw` — because animate-ui icons define their own variant
keys per glyph. `animateOnView` and `animateOnTap` SHALL NOT be
used unless an Architecture Decision Record explicitly approves
it for a specific call site.

When `window.matchMedia('(prefers-reduced-motion: reduce)').matches`
returns true, swapped icons SHALL render as static glyphs without
animation; this is enforced by the wrapper's built-in reduced-motion
handling and SHALL NOT be overridden at call sites.

#### Scenario: Hover triggers the wrapper's default animation

- **GIVEN** a meeting-detail page is rendered with the MetadataCard
  visible and the user has no reduced-motion preference
- **WHEN** the user hovers the Mic icon on the "開始會議" button
- **THEN** the icon SHALL render a path-draw animation that
  completes within one second
- **AND** moving the cursor off the icon SHALL allow the animation
  to finish naturally

#### Scenario: Reduced motion disables icon animation

- **GIVEN** the user has `prefers-reduced-motion: reduce` set
- **WHEN** the same Mic icon hover gesture occurs
- **THEN** the icon SHALL render its final static glyph state with
  no transition

#### Scenario: Spec governance — adding a new user-facing icon

- **GIVEN** a new feature introduces a user-facing action button
  that needs an icon NOT in the current 15-icon set
- **WHEN** an implementer chooses an icon for that button
- **THEN** the implementer SHALL install the animate-ui counterpart
  via the registry pattern `bunx shadcn@latest add @animate-ui/icons-<name>`
  and update the 15-icon list in this requirement
- **AND** SHALL NOT add the icon as a fresh lucide-react import
  for the user-action use case

#### Scenario: Group C icons stay on lucide-react

- **GIVEN** the codebase after this change ships
- **WHEN** the source is scanned for imports from `lucide-react`
- **THEN** the only icons still imported SHALL be drawn from this
  fixed list: `Check`, `ChevronUp`, `ChevronDown`, `ChevronLeft`,
  `ChevronRight`, `Columns3`, `Rows3`, `Sun`, `Moon`, `Monitor`,
  `Calendar`, `Mic`, `Square`, `Shield`, `ShieldCheck`, `Languages`

<!-- @trace
source: animate-ui-icons-swap
updated: 2026-05-12
code:
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/components/animate-ui/icons/log-out.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/animate-ui/icons/icon.tsx
  - packages/web/src/components/animate-ui/primitives/animate/slot.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/totp/verify.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/tsconfig.json
  - packages/web/src/components/back-link.tsx
  - packages/web/src/hooks/use-is-in-view.tsx
  - packages/web/src/components/animate-ui/icons/sparkles.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/animate-ui/icons/download.tsx
  - packages/web/src/components/animate-ui/icons/arrow-left.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - packages/web/vite.config.ts
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/components/animate-ui/icons/refresh-cw.tsx
  - packages/web/src/components/animate-ui/icons/copy.tsx
  - packages/web/src/components/animate-ui/icons/loader.tsx
  - packages/web/src/components/animate-ui/icons/plus.tsx
  - packages/web/src/components/animate-ui/icons/trash.tsx
  - packages/web/src/components/animate-ui/icons/lock.tsx
tests:
  - packages/web/src/components/animate-ui/icons/icon.test.tsx
  - packages/web/src/components/animate-ui/primitives/animate/slot.test.tsx
  - packages/web/src/components/animate-ui/icons/icons-smoke.test.tsx
  - packages/web/src/hooks/use-is-in-view.test.tsx
-->