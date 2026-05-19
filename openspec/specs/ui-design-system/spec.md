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

The token catalogue in `packages/web/src/index.css` SHALL declare two complete theme blocks selected via the `data-theme` attribute on `documentElement`. Both themes SHALL be anchored to the Aura colour family (per DESIGN.md §2, derived from `daltonmenezes/aura-theme`):

- `[data-theme="dark"]` (canonical mode per DESIGN.md §1) — primary hue centred on violet (`--primary-hue-dark: 290`), background `oklch(0.17 0.015 290)` (Ink Violet `#15141B`), surface stepped up by lightness, foreground near-white with the same purple tint (`oklch(0.93 0.003 295)`).
- `[data-theme="light"]` (mirror, also applied to bare `:root` so SSR-style flashes default to light) — primary hue centred on violet soft (`--primary-hue: 290`), background `oklch(0.97 0.003 295)` (Mist Bone `#EDECEE`), foreground deep violet-neutral (`oklch(0.20 0.015 290)`).

Both themes MUST share the same set of `--color-*` token names (dark/light parity). Every colour token SHALL be expressed in `oklch(...)` with explicit lightness / chroma / hue; raw hex literals SHALL NOT appear in component class strings or token definitions. Spacing, radius, and typography tokens SHALL be expressed as `--space-N`, `--radius-N`, `--text-N` CSS variables consumed by components.

The token set SHALL include at minimum: `--color-background`, `--color-surface`, `--color-surface-2`, `--color-surface-3`, `--color-foreground`, `--color-muted-foreground`, `--color-subtle-foreground`, `--color-border`, `--color-border-strong`, `--color-primary`, `--color-primary-hover`, `--color-primary-soft`, `--color-primary-foreground`, `--color-secondary`, `--color-secondary-foreground`, `--color-accent`, `--color-accent-foreground`, `--color-success`, `--color-success-soft`, `--color-warning`, `--color-warning-soft`, `--color-danger`, `--color-danger-soft`, `--color-info`, `--color-info-soft`, `--color-me`, `--color-me-soft`, `--color-them`, `--color-them-soft`, `--color-muted`, `--color-recording`.

#### Scenario: Dark theme renders Aura violet on Ink Violet background

- **GIVEN** a fresh browser session with `data-theme="dark"` applied to `documentElement`
- **WHEN** the computed style of `body` is inspected
- **THEN** `background-color` SHALL resolve to `oklch(0.17 0.015 290)` (Ink Violet) AND `--color-primary` SHALL resolve to `oklch(0.65 0.22 290)` (Aura Purple, vibrant)

#### Scenario: Light theme renders Aura violet soft on Mist Bone background

- **GIVEN** a fresh browser session with `data-theme="light"` applied to `documentElement`
- **WHEN** the computed style of `body` is inspected
- **THEN** `background-color` SHALL resolve to `oklch(0.97 0.003 295)` (Mist Bone) AND `--color-primary` SHALL resolve to `oklch(0.50 0.18 290)` (Aura Violet Soft)

#### Scenario: No raw hex colour appears in component class strings

- **GIVEN** the production bundle of `packages/web` after build
- **WHEN** the bundled CSS is scanned for hex colour literals (`#[0-9a-fA-F]{3,8}` patterns) inside component class attributes
- **THEN** the only matches SHALL be inside `index.css` token definitions, inline SVG fill / stroke attributes used by brand logos (Google sign-in icon) or `tag-palette.ts` (an isolated palette domain), CSS mask alpha values (`#000` in `border-beam`), and `rgba()` literals inside `--shadow-*` declarations; no component-level `className` SHALL contain a raw hex outside this explicit allowlist

#### Scenario: Dark and light theme blocks declare identical token keys

- **GIVEN** `packages/web/src/index.css` after this change ships
- **WHEN** an automated parser extracts every `--color-*` declaration name from the `[data-theme="dark"]` and `[data-theme="light"]` (and `:root`) blocks
- **THEN** the symmetric difference of the two key sets SHALL be empty (every token defined in one theme is defined in the other)

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

The speaker tokens SHALL be anchored to invariant hue families across both themes (per DESIGN.md §2):

- `--color-me` SHALL resolve to a blue hue (hue 220, Glacier Blue family) — `oklch(0.86 0.12 220)` in dark theme, `oklch(0.65 0.10 220)` in light theme.
- `--color-them` SHALL resolve to a magenta hue (hue 320, Magenta Bloom family) — `oklch(0.77 0.22 320)` in dark theme, `oklch(0.55 0.15 320)` in light theme.

`--color-them` SHALL be measurably more saturated than `--color-me` (chroma differential SHALL exceed 0.05 in either theme) so users can scan dialogue ownership at a glance. Speaker tokens SHALL NOT be derived from `--primary-hue` (they are independent of the primary theme hue and remain stable when `--primary-hue` is tuned via design-canvas).

#### Scenario: Counterparty chunk carries all four visual cues in magenta

- **GIVEN** a transcript chunk with `speaker = "counterparty"` rendered in the default light theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the chunk wrapper SHALL have:
  - `border-left-width: 3px` AND `border-left-color` resolving to `oklch(0.55 0.15 320)` (`--color-them`) AND
  - `background-color` resolving to a non-transparent mix of `--color-them-soft` AND
  - a `[data-testid="speaker-dot"]` element with background `--color-them` rendered before the name AND
  - the speaker name element with `font-weight: 600` and colour `--color-them`

#### Scenario: Me chunk uses Glacier Blue in either theme

- **GIVEN** a transcript chunk with `speaker = "me"` rendered in dark theme
- **WHEN** the rendered DOM and computed styles are inspected
- **THEN** the same four cues SHALL apply but using `--color-me` resolving to `oklch(0.86 0.12 220)` AND `--color-me-soft` for the background; the visual hierarchy SHALL clearly place 對方 (magenta) as the focal point relative to 我方 (blue)

#### Scenario: Speaker tokens are independent of primary hue

- **GIVEN** the design-canvas runtime knob is used to set `--primary-hue: 200` (an arbitrary blue) on `documentElement`
- **WHEN** the computed style of any rendered transcript chunk is inspected
- **THEN** `--color-me` SHALL still resolve to a blue with hue 220 (NOT 200) AND `--color-them` SHALL still resolve to a magenta with hue 320 — speaker tokens are NOT derived from `--primary-hue`

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

---
### Requirement: --color-secondary SHALL be a distinct teal hue, not a surface-2 alias

The web app SHALL define `--color-secondary` and
`--color-secondary-foreground` as standalone oklch values keyed to
hue 195 (teal/cyan) in BOTH the `[data-theme="light"]` and
`[data-theme="dark"]` token blocks of `packages/web/src/index.css`.
The pre-change binding (`var(--color-surface-2)`) SHALL be removed.
Any UI that previously consumed `--color-secondary` as a neutral
surface MUST migrate to `--color-muted` or `--color-surface-2`
directly.

Concrete values:

- Light theme: `--color-secondary: oklch(0.62 0.12 195);`
  `--color-secondary-foreground: oklch(1 0 0);`
- Dark theme: `--color-secondary: oklch(0.7 0.13 195);`
  `--color-secondary-foreground: oklch(0.14 0.012 var(--primary-hue-dark));`

Hue 195 was chosen because it is roughly opposite both light-theme
primary (purple, hue 280) and dark-theme primary (orange, hue 50)
on the oklch wheel, so the secondary action stays visually distinct
from primary in either theme. It is also far enough from
`--color-success` (green, hue 155) to avoid confusion.

`Button variant="secondary"` SHALL render with the new token,
producing a teal pill in both themes. Other Button variants
(primary / outline / ghost / destructive) SHALL NOT change.

#### Scenario: Light-theme secondary button renders teal

- **GIVEN** the user has the light theme active and views any
  page that renders a `<Button variant="secondary">`
- **WHEN** the button is in its default (non-hover) state
- **THEN** its background SHALL resolve to `oklch(0.62 0.12 195)`
  and its foreground SHALL resolve to white

#### Scenario: Dark-theme secondary button renders teal

- **GIVEN** the user has the dark theme active and views the same
  page
- **WHEN** the button is in its default (non-hover) state
- **THEN** its background SHALL resolve to `oklch(0.7 0.13 195)`
  and its foreground SHALL resolve to the dark-theme background
  colour

#### Scenario: Other button variants are unaffected

- **GIVEN** the codebase after this change ships
- **WHEN** the source is scanned for Button `variant="primary"`,
  `variant="outline"`, `variant="ghost"`, and `variant="destructive"`
  call sites
- **THEN** each variant SHALL render the same colour as before this
  change in both themes

<!-- @trace
source: meetings-ux-revamp
updated: 2026-05-12
code:
  - packages/web/public/logo.png
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/public/favicon.png
  - packages/web/src/index.css
  - packages/web/src/locales/en.json
  - packages/web/index.html
  - assets/meeting-playbook-logo-favicon.png
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/routes/meetings/new.tsx
  - assets/meeting-playbook-logo.png
  - packages/web/src/routes/login.tsx
tests:
  - packages/web/src/components/meetings-view-tabs.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
-->

---
### Requirement: `--color-accent` SHALL be an independent magenta token, not a primary alias

The token catalogue in `packages/web/src/index.css` SHALL declare `--color-accent` and `--color-accent-foreground` as standalone oklch values in both theme blocks; the pre-change binding (`--color-accent: var(--color-primary)`) SHALL be removed. The accent token SHALL anchor to the magenta hue family (hue 320, Magenta Bloom / Mauve Soft per DESIGN.md §2):

- Dark theme: `--color-accent: oklch(0.77 0.22 320);` `--color-accent-foreground: oklch(0.17 0.015 290);`
- Light theme: `--color-accent: oklch(0.55 0.15 320);` `--color-accent-foreground: oklch(1 0 0);`

Components consuming `bg-(--color-accent)`, `text-(--color-accent)`, `border-(--color-accent)` SHALL render with magenta in dark theme and mauve in light theme — visibly distinct from `--color-primary` (violet) in either theme.

#### Scenario: Accent renders magenta in dark theme

- **GIVEN** an element with `className="bg-(--color-accent)"` rendered in dark theme
- **WHEN** its computed `background-color` is inspected
- **THEN** the value SHALL resolve to `oklch(0.77 0.22 320)` (Magenta Bloom) AND SHALL NOT equal `--color-primary`

#### Scenario: Accent renders mauve soft in light theme

- **GIVEN** the same element rendered in light theme
- **WHEN** its computed `background-color` is inspected
- **THEN** the value SHALL resolve to `oklch(0.55 0.15 320)` (Mauve Soft) AND SHALL NOT equal `--color-primary`

---
### Requirement: `--color-info` SHALL be a distinct status token decoupled from speaker me

The token catalogue SHALL declare `--color-info` and `--color-info-soft` in both theme blocks as standalone oklch values anchored to the Glacier Blue / Steel Blue hue family (hue 220). The info token SHALL be value-equal to `--color-me` in initial declaration but SHALL be declared independently so the speaker semantic and the status semantic can diverge in future changes without coupling:

- Dark theme: `--color-info: oklch(0.86 0.12 220);` `--color-info-soft: oklch(0.32 0.06 220);`
- Light theme: `--color-info: oklch(0.65 0.10 220);` `--color-info-soft: oklch(0.92 0.04 220);`

The `--color-info` token SHALL be referenced by status indicators (toast info variant, alert info variant, etc.) and SHALL NOT be referenced by transcript chunk speaker styling (which uses `--color-me` / `--color-them`).

#### Scenario: Info token declared independently from me token

- **GIVEN** `packages/web/src/index.css` after this change ships
- **WHEN** the file is grepped for the two literal declarations `--color-info:` and `--color-me:`
- **THEN** each SHALL appear at least once in both theme blocks AND each SHALL be a literal `oklch(...)` value (NOT a `var(--color-me)` alias)

---
### Requirement: Default radius scale SHALL be sharp 4 / 6 / 8 / 12

The token catalogue SHALL declare the default radius scale as `--radius-sm: 4px`, `--radius-md: 6px`, `--radius-lg: 8px`, `--radius-xl: 12px`, `--radius-pill: 999px` (per DESIGN.md `rounded` mapping). The `[data-radius="sharp"]` knob SHALL produce a sharper variant (`2px` / `4px` / `6px` / `8px`) and `[data-radius="soft"]` SHALL retain the previous softer scale (`6px` / `12px` / `16px` / `20px`) so existing usage sites remain functional.

#### Scenario: Cards render with 8px radius by default

- **GIVEN** any `<Card>` rendered without `[data-radius]` attribute
- **WHEN** its computed `border-radius` is inspected
- **THEN** the value SHALL resolve to `8px` (`--radius-lg`)

#### Scenario: Buttons render with 4px radius by default

- **GIVEN** any `<Button>` rendered without `[data-radius]` attribute
- **WHEN** its computed `border-radius` is inspected
- **THEN** the value SHALL resolve to `4px` (`--radius-sm`)

---
### Requirement: Dark theme SHALL favour inset hairlines over drop shadows, light theme SHALL retain soft drop shadows

The token catalogue SHALL declare `--shadow-sm`, `--shadow-md`, `--shadow-lg` per DESIGN.md §1 `shadow` mapping:

- **Dark theme**:
  - `--shadow-sm: none`
  - `--shadow-md: 0 1px 0 rgba(0,0,0,0.3) inset` (inset hairline only)
  - `--shadow-lg: 0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.4)` (1px outline ring + soft drop)
- **Light theme**:
  - `--shadow-sm: 0 1px 2px rgba(20,14,40,0.04)`
  - `--shadow-md: 0 4px 16px rgba(20,14,40,0.06), 0 1px 3px rgba(20,14,40,0.04)`
  - `--shadow-lg: 0 12px 32px rgba(20,14,40,0.1), 0 2px 6px rgba(20,14,40,0.06)`

`--shadow-focus` SHALL remain a 3px oklch primary 25%-opacity ring in both themes. Card / Dialog / Popover surface separation in dark theme SHALL come primarily from the background-vs-surface lightness step, not drop shadows.

`rgba()` inside `--shadow-*` SHALL be a permitted exception to the "no raw rgb/rgba" rule (CSS shadow specification has incomplete oklch support across browsers).

#### Scenario: Dark theme card has no visible drop shadow

- **GIVEN** a `<Card>` rendered with `shadow-sm` Tailwind utility in dark theme
- **WHEN** its computed `box-shadow` is inspected
- **THEN** the value SHALL resolve to `none`

#### Scenario: Light theme card has subtle drop shadow

- **GIVEN** the same `<Card>` rendered with `shadow-sm` Tailwind utility in light theme
- **WHEN** its computed `box-shadow` is inspected
- **THEN** the value SHALL resolve to `0 1px 2px rgba(20, 14, 40, 0.04)` (non-zero alpha drop shadow)

---
### Requirement: Sonner Toaster SHALL render four semantic colour variants via CSS data-attribute selectors

The web app SHALL provide four semantic Sonner toast variants — `info`, `success`, `warning`, `error` — each mapped to the corresponding Aura semantic token (`--color-info` / `--color-success` / `--color-warning` / `--color-danger`). The mapping SHALL be applied via CSS data-attribute selectors in `packages/web/src/index.css`, overriding Sonner's internal `--normal-bg`, `--normal-border`, `--normal-text` custom properties.

The selector pattern SHALL be:

`[data-sonner-toast][data-type="success"]` sets `--normal-bg: var(--color-success-soft); --normal-border: var(--color-success); --normal-text: var(--color-foreground);`

The same pattern SHALL apply to `data-type="error"` (mapped to `--color-danger` + `--color-danger-soft`), `data-type="warning"` (mapped to `--color-warning` + `--color-warning-soft`), and `data-type="info"` (mapped to `--color-info` + `--color-info-soft`). The `<Toaster>` React component in `packages/web/src/components/ui/sonner.tsx` SHALL NOT have its JSX structure, motion, or behaviour changed in this requirement (deferred to a later phase). Each variant SHALL be visually distinct in both light and dark themes.

#### Scenario: Success toast renders with green accent

- **GIVEN** `toast.success("Saved")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-success-soft` AND its border SHALL resolve to `--color-success`

#### Scenario: Error toast renders with red accent

- **GIVEN** `toast.error("Failed")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-danger-soft` AND its border SHALL resolve to `--color-danger`

#### Scenario: Warning toast renders with orange accent

- **GIVEN** `toast.warning("Quota near limit")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-warning-soft` AND its border SHALL resolve to `--color-warning`

#### Scenario: Info toast renders with blue accent

- **GIVEN** `toast.info("Processing started")` is invoked
- **WHEN** the rendered Sonner toast DOM element is inspected
- **THEN** its computed background SHALL resolve to `--color-info-soft` AND its border SHALL resolve to `--color-info`

---
### Requirement: oklch validation smoke test SHALL guard token format and dark/light parity

The web workspace SHALL ship an automated test (at `packages/web/src/lib/tokens.test.ts` or an equivalent path discoverable by the `bun test` runner) that validates the design token discipline as part of CI. The test SHALL:

1. Read `packages/web/src/index.css` as plain text.
2. Assert that every `--color-*` declaration value matches the pattern `oklch(...)` OR `var(--color-*)` OR a permitted CSS keyword (`none`, `transparent`).
3. Assert dark/light parity: the set of `--color-*` declaration names inside `[data-theme="dark"]` SHALL equal the set inside `[data-theme="light"]` (and `:root`).
4. Scan every file under `packages/web/src/` matching the glob `**/*.{ts,tsx}` (excluding `**/*.test.*`) for raw hex (`#[0-9a-fA-F]{3,8}`), `rgb(`, and `rgba(` occurrences in source code. Matches SHALL be empty unless the file is on the explicit allowlist documented inline in the test with justification:
   - `packages/web/src/lib/tag-palette.ts` — isolated tag palette domain.
   - `packages/web/src/components/magicui/border-beam.tsx` — CSS mask alpha (`#000` in `linear-gradient` inside `WebkitMask`).
   - `packages/web/src/routes/login.tsx` and `packages/web/src/routes/settings/profile.tsx` — Google brand SVG fill values.

Any new allowlist entry added in future PRs SHALL include an inline comment stating the justification; otherwise the test fails.

#### Scenario: All `--color-*` tokens are oklch values

- **GIVEN** `packages/web/src/index.css` after the Aura tokens are applied
- **WHEN** the validation test runs
- **THEN** every line declaring a `--color-` token value SHALL match the permitted-value pattern AND the test SHALL pass

#### Scenario: Dark theme is missing a token that light theme has → test fails

- **GIVEN** a hypothetical edit that removes `--color-info-soft` from the `[data-theme="dark"]` block but leaves it in `[data-theme="light"]`
- **WHEN** the validation test runs
- **THEN** the test SHALL fail with a message that names the missing token

#### Scenario: New component file introduces raw hex without justification → test fails

- **GIVEN** a new file `packages/web/src/components/new-widget.tsx` containing a raw `#ff0000` literal in a className attribute
- **WHEN** the validation test runs
- **THEN** the test SHALL fail with a message that names the offending file and line

---
### Requirement: Dialog and AlertDialog SHALL use animate-ui motion with Aura tokens

The `packages/web/src/components/ui/dialog.tsx` barrel SHALL wrap the animate-ui base dialog primitive. Backdrop SHALL use `var(--color-background)` at 80% opacity with an 8px backdrop blur, content SHALL use `var(--color-surface)` background and `var(--radius-lg)` corner radius. Open / close transitions SHALL use the animate-ui scale + fade motion presets at the default 180ms duration; `prefers-reduced-motion: reduce` SHALL force instant transitions.

Every existing dialog callsite (including the meeting link picker, the playbook regenerate confirmation, and other surfaces opening a Dialog) SHALL import from the `ui/dialog` barrel rather than `@radix-ui/react-dialog` directly. Existing test selectors (`data-testid`, `role="dialog"`, accessible name) SHALL keep resolving so component tests pass without rewrites.

#### Scenario: Opening a Dialog renders animate-ui motion and Aura tokens

- **WHEN** the user opens the meeting link picker dialog
- **THEN** `[role="dialog"]` SHALL mount with computed `background-color` resolving to `var(--color-surface)` AND the backdrop SHALL render `backdrop-filter: blur(8px)` AND the dialog SHALL animate in with scale + fade

#### Scenario: Reduced motion disables dialog animation

- **GIVEN** the user has `prefers-reduced-motion: reduce` set at the OS level
- **WHEN** any Dialog opens
- **THEN** the Dialog SHALL appear at its final state immediately with no scale or fade transition

---
### Requirement: Popover SHALL ship via a barrel and use animate-ui motion

The web app SHALL add `packages/web/src/components/ui/popover.tsx` exporting `Popover` / `PopoverTrigger` / `PopoverContent` / `PopoverAnchor`, wrapping the animate-ui base popover primitive. Every popover consumer (transcript chunk action menu, speaker color popover, tag picker, transcript chunk row action surface, and any future popover) SHALL import from this barrel; direct imports of `@radix-ui/react-popover` SHALL be removed from feature components.

Popover content SHALL use `var(--color-surface)` background, `var(--color-border)` border, `var(--radius-md)` corner radius, and the animate-ui origin-based scale + opacity entrance. Z-index SHALL keep popover above transcript chunk rows but below modal dialogs.

#### Scenario: Tag picker popover opens via the barrel and reads tokens

- **WHEN** the user clicks the tag picker trigger
- **THEN** a `[role="dialog"]` from the animate-ui popover SHALL mount AND computed `background-color` SHALL resolve to `var(--color-surface)` AND no DOM nodes SHALL originate from `@radix-ui/react-popover` direct imports inside feature components

#### Scenario: Transcript chunk action menu opens via the barrel

- **WHEN** the user opens the action menu for a transcript chunk
- **THEN** the popover content SHALL render with the animate-ui scale entrance AND the trigger SHALL retain its existing `data-testid` so e2e selectors continue to resolve

---
### Requirement: Tooltip SHALL wrap every hover-info button across the app

`packages/web/src/components/ui/tooltip.tsx` SHALL wrap the animate-ui primitives/animate/tooltip and SHALL be applied to every icon-only button, badge, or hover-info control that conveys supplementary information. The audit MUST cover at least: the recording badge, the dual-channel capture indicator, the rerun transcript button, the theme toggle button, and the locale toggle button. Tooltip background SHALL use `var(--color-foreground)` and tooltip text SHALL use `var(--color-background)` (inverse) per DESIGN.md §4. Every tooltip content string SHALL be backed by an i18n key with parity in both `zh-TW.json` and `en.json`.

#### Scenario: Icon-only buttons surface a tooltip on hover

- **WHEN** the user hovers any icon-only button across the audited surfaces (recording badge, capture indicator, rerun button, theme toggle, locale toggle, and any other listed in the audit task)
- **THEN** an animate-ui tooltip SHALL render with text resolved from a `t("ui.tooltip.*")` key AND the tooltip SHALL use inverse colours (foreground background, background text)

#### Scenario: Tooltip strings exist in both locales

- **WHEN** `locales.test.ts` runs the deep-equal parity guard
- **THEN** every `ui.tooltip.*` key SHALL be present in both `zh-TW.json` and `en.json` with equal structure

---
### Requirement: Determinate Progress SHALL use animate-ui base progress

The web app SHALL add `packages/web/src/components/ui/progress.tsx` wrapping the animate-ui base progress primitive. The bar fill SHALL use `var(--color-primary)`, the track SHALL use `var(--color-surface-2)`, the height SHALL be 4px by default, and corner radius SHALL be `var(--radius-pill)`. The component SHALL accept `value` (0..100) and an `aria-label` prop. Indeterminate behavior SHALL be rejected for this component; long-running operations without a known total SHALL use the indeterminate Loading component instead.

#### Scenario: Progress renders fill proportional to value

- **WHEN** `<Progress value={42} aria-label="Generating playbook" />` mounts
- **THEN** the rendered bar SHALL have computed width near 42% of the track AND `[role="progressbar"]` SHALL carry `aria-valuenow="42"` AND the fill background SHALL resolve to `var(--color-primary)`

---
### Requirement: Indeterminate Loading SHALL be a ported uiverse animation in Aura purple

The web app SHALL add `packages/web/src/components/ui/loading.tsx`, a React + Tailwind port of `https://uiverse.io/gustavofusco/rare-pug-90`. The animation SHALL run on `var(--color-primary)` (Aura purple) rather than the original colours. The source file SHALL include a top-of-file comment stating `Source: https://uiverse.io/gustavofusco/rare-pug-90 (CC0)` for license attribution. Sizes `sm` / `md` / `lg` SHALL be exposed via a `size` prop. The component SHALL respect `prefers-reduced-motion: reduce` by rendering a static dot or `Skeleton` fallback with no animation.

#### Scenario: Loading respects reduced motion

- **GIVEN** the user has `prefers-reduced-motion: reduce` set
- **WHEN** `<Loading aria-label="Loading transcript" />` mounts
- **THEN** the DOM SHALL render the fallback static element with no animation styles applied AND the accessible name SHALL still be exposed via the `aria-label`

#### Scenario: Loading uses Aura purple

- **WHEN** the component mounts in the default dark theme without reduced motion
- **THEN** the computed colour of the animated dots SHALL resolve to `var(--color-primary)` and no raw hex literal SHALL appear in the component class strings

---
### Requirement: Theme toggler SHALL be the magicui animated reveal switch limited to two states

`packages/web/src/components/theme-toggle.tsx` SHALL be replaced by an implementation using `https://magicui.design/docs/components/animated-theme-toggler`. The toggle UI SHALL expose only `dark` and `light` states; the `system` state SHALL no longer be reachable through the toggle (fresh sessions SHALL still fall back to `prefers-color-scheme` until the first click). The button SHALL carry an `aria-label` resolved from `t("ui.themeToggle.label")` and the action labels SHALL come from `t("ui.themeToggle.toLight")` / `t("ui.themeToggle.toDark")`. Click SHALL trigger the circular reveal animation; reduced motion SHALL collapse the reveal into an instant swap.

`ThemeProvider`'s `theme` type SHALL remain `"light" | "dark" | "system"` to keep persistence backward-compatible; only the toggle UI surface SHALL be reduced to two states.

#### Scenario: Clicking the toggle alternates between dark and light only

- **GIVEN** the application is in the default dark theme after a fresh load
- **WHEN** the user clicks the theme toggle once and then again
- **THEN** `documentElement` `data-theme` SHALL change to `"light"` and then back to `"dark"` AND `localStorage.mp-theme` SHALL store the explicit choice (no `"system"` value SHALL be written by the toggle)

#### Scenario: Theme toggle accessible name is localised

- **WHEN** the toggle renders in the en locale and then in the zh-TW locale
- **THEN** the button's accessible name SHALL resolve to the value of `ui.themeToggle.label` from the active locale file AND both `zh-TW.json` and `en.json` SHALL contain that key

---
### Requirement: Toast SHALL expose four semantic variants tied to Aura semantic tokens

`packages/web/src/components/ui/sonner.tsx` SHALL surface four semantic toast variants — `info`, `success`, `warning`, `error` — each callable as `toast.info(...)` / `toast.success(...)` / `toast.warning(...)` / `toast.error(...)`. Each variant SHALL render with a left-edge stripe whose colour resolves to `var(--color-info)`, `var(--color-success)`, `var(--color-warning)`, or `var(--color-danger)` respectively. Every existing direct `toast(...)` callsite in feature components (export meeting button, playbook pane, offline ingest upload dialog, and any others) SHALL be migrated to the appropriate semantic helper. The legacy `toast(...)` passthrough SHALL remain callable to avoid build breakage during migration but SHALL render with no stripe.

JSX wrappers `<ToastInfo>` / `<ToastSuccess>` / `<ToastWarning>` / `<ToastError>` SHALL be provided in `packages/web/src/components/ui/toast-variants.tsx` for declarative callsites. Each variant SHALL carry an `aria-label` resolved from `t("ui.toast.<variant>.label")` (info / success / warning / error), with parity in both locale files.

#### Scenario: Success toast renders the success stripe and aria-label

- **WHEN** a feature component calls `toast.success(t("playbook.regen.done.body"))`
- **THEN** the rendered toast node SHALL carry `data-type="success"` AND a visible stripe whose computed colour resolves to `var(--color-success)` AND its accessible name SHALL resolve to the `ui.toast.success.label` key from the active locale

#### Scenario: Error toast renders the danger stripe

- **WHEN** the export meeting mutation fails and the component calls `toast.error(...)`
- **THEN** the rendered toast SHALL carry `data-type="error"` AND a stripe whose computed colour resolves to `var(--color-danger)`

#### Scenario: Toast locale parity holds

- **WHEN** `locales.test.ts` runs the deep-equal guard
- **THEN** `ui.toast.info.label`, `ui.toast.success.label`, `ui.toast.warning.label`, and `ui.toast.error.label` SHALL exist in both `zh-TW.json` and `en.json`

---
### Requirement: Date selection in meeting forms SHALL use the Aura calendar picker

`packages/web/src/components/ui/calendar.tsx` SHALL ship a wrapper over `https://www.shadcnblocks.com/component/calendar/calendar-standard-3` styled with Aura tokens (`--color-primary` for selected day, `--color-surface` for the panel, `--color-border` for cell borders, `--radius-md` for the panel corners). The source file SHALL include a top-of-file comment stating `Source: https://www.shadcnblocks.com/component/calendar/calendar-standard-3`.

The meeting edit form and `routes/meetings/new.tsx` SHALL replace each `<input type="datetime-local">` with the combination of `<Calendar />` (date) and `<Input type="time" />` (time). The form submit handler SHALL combine the date and time into an ISO datetime string so the backend payload shape remains unchanged. The calendar SHALL expose `aria-label`, prev / next month buttons, and a "today" shortcut, all backed by i18n keys (`ui.calendar.openPicker`, `ui.calendar.clear`, `ui.calendar.today`).

#### Scenario: Selecting a date and time produces the same ISO submit payload

- **GIVEN** the user opens the meeting edit form with `scheduled_start_at = "2026-05-20T14:30:00+08:00"`
- **WHEN** the user selects date `2026-05-22` via the calendar AND types time `09:00` into the time input AND submits the form
- **THEN** the form SHALL send `scheduled_start_at = "2026-05-22T09:00:00+08:00"` (or equivalent ISO datetime) to the backend AND the backend payload shape SHALL be unchanged from the prior `datetime-local` behaviour

#### Scenario: Calendar locale strings parity

- **WHEN** `locales.test.ts` runs the parity guard
- **THEN** `ui.calendar.openPicker`, `ui.calendar.clear`, and `ui.calendar.today` SHALL exist in both `zh-TW.json` and `en.json`

---
### Requirement: Vendor install spike SHALL gate the production primitive work

Before any feature code in this change is committed to a production branch, a Task 0 spike SHALL verify that the `@animate-ui` base dialog, the magicui animated theme toggler, and the shadcnblocks `calendar-standard-3` snippet all install via the shadcn-compatible CLI without peer dependency conflicts. The spike SHALL confirm that `bun run build`, `bunx tsc --noEmit`, and the dev server start all pass with the vendor packages added, and that Tailwind v4 token override syntax (`bg-(--color-surface)` and equivalents) resolves correctly inside the vendor components.

If the spike surfaces conflicts (peer dep clashes, Tailwind v4 incompatibility, or a license header indicating a shadcnblocks Pro tier), the change SHALL pause and the conflict SHALL be reported back before production work continues.

#### Scenario: Spike succeeds and production tasks proceed

- **WHEN** the spike branch installs the three vendor packages AND `bun run build`, `bunx tsc --noEmit`, and the dev server start all return success
- **THEN** the spike SHALL be marked complete and the production primitive tasks SHALL be allowed to begin

#### Scenario: Spike fails and production work pauses

- **WHEN** the spike branch surfaces any peer dependency conflict OR a license incompatibility OR a build failure attributable to the new vendor packages
- **THEN** production tasks SHALL NOT begin AND the conflict SHALL be surfaced to the change owner for a decision (alternative vendor, fallback to existing primitive, or escalate)

##### Example: shadcnblocks calendar block is gated behind a paid tier

- **GIVEN** the spike has installed `@animate-ui` base dialog (no conflict) AND magicui animated-theme-toggler (no conflict) AND attempts to fetch shadcnblocks `calendar-standard-3`
- **WHEN** the shadcnblocks page license header reads "Pro tier, paid license required"
- **THEN** the spike SHALL stop before adding the snippet, the change owner SHALL be notified, and the production primitive tasks SHALL remain blocked until either (a) the calendar is replaced by the shadcn-internal `calendar` component or (b) the change owner approves the license cost
