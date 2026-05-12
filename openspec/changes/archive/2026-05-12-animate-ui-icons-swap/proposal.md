## Summary

Swap user-facing lucide-react icons in the web package for the
`@animate-ui/icons-*` registry equivalents so action buttons, hero
glyphs, and status indicators feel alive on hover / tap.

## Motivation

After the UI overhaul (change `ui-overhaul-claude-design`), Sean
reviewed the rendered surface and flagged the icon glyphs as static
and visually inert ("好多都好醜"). lucide-react ships clean static
SVGs but no motion; animate-ui re-skins the same lucide library with
Motion-driven micro-interactions (path-draw on hover, scale on tap,
loop variants on streaming spinners). Reusing the same underlying
glyphs preserves brand consistency while raising the perceived
polish of the most prominent action affordances.

## Proposed Solution

Install the animate-ui icon wrapper plus a curated set of 15 icon
components in `packages/web/src/components/animate-ui/icons/` and
sweep the codebase replacing lucide imports for those names. Imports
for icons that only live inside shadcn primitives (Check, Chevron*,
Columns3 / Rows3, Sun / Moon / Monitor) stay on lucide-react —
those are static markers, not user-action triggers, and swapping
them would force a rewrite of the primitives' internal markup.

The wrapper depends on Motion-React; the project already ships
framer-motion 12 which is the same library under a different
package name. The wrapper SHALL import from `motion/react` and the
project SHALL add a `motion` dependency that re-exports
framer-motion's surface (or installs the standalone `motion` npm
package — design phase to pick one).

Visual contract: animations trigger on hover only by default
(`animateOnHover`), respect `prefers-reduced-motion: reduce` via the
wrapper's built-in hook, and fall back to a static glyph identical
to the current lucide render when motion is disabled. Existing tests
that assert `<svg>` presence (e.g. transcript chunks, theme toggle)
keep passing because animate-ui still renders an `<svg>` root.

## Non-Goals

- NOT swapping icons inside shadcn primitives (select, dropdown-menu,
  theme-toggle's tray, layout-switcher's two buttons) — those are
  structural markers, not user-action targets.
- NOT changing icon library across the entire codebase — lucide-react
  stays the dependency for the 11 icons in Group C (Check, ChevronUp,
  ChevronDown, ChevronLeft, ChevronRight, Columns3, Rows3, Sun, Moon,
  Monitor, Calendar) plus future internal use.
- NOT writing motion variants for every icon — the wrapper's default
  `path` / `path-loop` presets cover the curated 15 without custom
  per-icon authoring.
- NOT touching the existing ui-design-system spec's animation library
  policy (framer-motion / magicui / animate-ui split). This change
  refines the animate-ui usage to also cover icon glyphs.

## Alternatives Considered

- **Custom per-icon framer-motion variants**: more control but ~3x
  the code; rejected because the wrapper's default path-draw matches
  the design bundle's intent.
- **CSS-only hover transforms on lucide icons**: cheap but only gives
  scale / translate, not the path-draw effect Sean asked for.
- **Full lucide → animate-ui swap (all 26 icons)**: rejected because
  primitives' internal icons add noise to the diff without visual
  gain.

## Impact

- Affected specs: `ui-design-system` (extended icon-library policy)
- Affected code:
  - New:
    - packages/web/src/components/animate-ui/icons/icon.tsx (wrapper)
    - packages/web/src/components/animate-ui/icons/slot.tsx (primitive)
    - packages/web/src/hooks/use-is-in-view.ts (intersection hook)
    - packages/web/src/components/animate-ui/icons/arrow-left.tsx
    - packages/web/src/components/animate-ui/icons/copy.tsx
    - packages/web/src/components/animate-ui/icons/download.tsx
    - packages/web/src/components/animate-ui/icons/languages.tsx
    - packages/web/src/components/animate-ui/icons/loader.tsx
    - packages/web/src/components/animate-ui/icons/lock.tsx
    - packages/web/src/components/animate-ui/icons/log-out.tsx
    - packages/web/src/components/animate-ui/icons/mic.tsx
    - packages/web/src/components/animate-ui/icons/plus.tsx
    - packages/web/src/components/animate-ui/icons/refresh-cw.tsx
    - packages/web/src/components/animate-ui/icons/shield.tsx
    - packages/web/src/components/animate-ui/icons/shield-check.tsx
    - packages/web/src/components/animate-ui/icons/sparkles.tsx
    - packages/web/src/components/animate-ui/icons/square.tsx
    - packages/web/src/components/animate-ui/icons/trash.tsx
  - Modified:
    - packages/web/package.json (add motion dependency)
    - packages/web/src/components/back-link.tsx
    - packages/web/src/components/metadata-card.tsx
    - packages/web/src/components/protected-shell.tsx
    - packages/web/src/components/summary-pane.tsx
    - packages/web/src/components/locale-toggle.tsx
    - packages/web/src/routes/home.tsx
    - packages/web/src/routes/login.tsx
    - packages/web/src/routes/signup.tsx
    - packages/web/src/routes/calendar/upcoming.tsx
    - packages/web/src/routes/meetings/list.tsx
    - packages/web/src/routes/meetings/calendar.tsx
    - packages/web/src/routes/meetings/new.tsx
    - packages/web/src/routes/totp/enroll.tsx
    - packages/web/src/routes/totp/verify.tsx
    - openspec/specs/ui-design-system/spec.md (icon-library policy ADD)
  - Removed: (none)
