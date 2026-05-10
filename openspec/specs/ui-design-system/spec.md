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