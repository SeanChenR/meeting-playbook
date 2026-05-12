## ADDED Requirements

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
