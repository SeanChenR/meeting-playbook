## Context

The web package consumes 26 distinct lucide-react icons across 18
files (components + routes). After the UI overhaul shipped, Sean
reviewed the rendered surface and asked for animate-ui icons because
lucide glyphs feel "lifeless" next to the framer-motion-driven
panes, badges, and Tabs cross-fade. animate-ui ships every lucide
icon as a Motion-React component with default path-draw / scale /
loop variants, controllable via `animateOnHover`, `animateOnTap`,
or `animateOnView` props. Each icon is installed individually via
the shadcn-compatible registry at `https://animate-ui.com/r/icons-<name>.json`.

The wrapper component (`icons-icon`) lives at
`components/animate-ui/icons/icon.tsx`, imports from `motion/react`,
and depends on:
- A `Slot` primitive for `asChild` composition
- A `useIsInView` hook for view-triggered animations
- The `motion` npm package (separate from `framer-motion`, even
  though they ship the same underlying library — Motion v12 is the
  rebranded fork that animate-ui aligns with)

The project currently has `framer-motion@12.38.0`. Motion-React
exports the same API surface; the two packages are interchangeable
at the import level but Bun resolves them as distinct modules unless
a peer alias is configured.

Existing icons split into three usage groups:

- **Group A — user-facing action triggers (10)**: Sparkles, Mic,
  Square, RefreshCw, Plus, ArrowLeft, Copy, Download, Trash2, LogOut
- **Group B — hero / status glyphs (5)**: Lock, Shield, ShieldCheck,
  Languages, Loader2
- **Group C — structural primitives' internals (11)**: Check,
  ChevronUp / ChevronDown / ChevronLeft / ChevronRight, Columns3,
  Rows3, Sun, Moon, Monitor, Calendar

Groups A + B (15 icons) are the swap target. Group C stays on
lucide-react because:
- Select / DropdownMenu / Tabs internals don't have user-action
  semantics — they're rendered passively per state.
- Replacing them would force editing the shadcn primitive markup,
  inflating the diff without visual payoff.
- Theme toggle's Sun / Moon / Monitor swap with each click anyway;
  a path-draw animation would compete with the swap motion.

## Goals

- Replace the 15 in-scope lucide imports with animate-ui icon
  components across 14 modified files.
- Centralise the wrapper + 3 helpers (Slot, useIsInView) so future
  per-icon installs follow the same path convention.
- Keep all existing unit tests green without selector edits — the
  wrapper still renders an `<svg>` root, so DOM queries that look
  for `<svg>` or specific aria-labels continue to resolve.
- Add an icon-library policy requirement to `ui-design-system`
  spec so future contributors know which icons go to which library.
- Honour `prefers-reduced-motion: reduce` — the wrapper already
  reads the media query and short-circuits motion when set.

## Non-Goals

- NOT swapping Group C icons (11) — out of scope.
- NOT authoring custom per-icon variants — default `path` /
  `path-loop` presets are sufficient.
- NOT extending animations to non-icon SVG elements (e.g. the
  inline logo glyph in NavBar / login card).
- NOT touching backend / auth / route-tree.

## Decisions

### Decision 1: Add `motion` package vs alias from `framer-motion`

The animate-ui icon wrapper imports from `motion/react`. Options:

**A)** Install `motion` (npm) alongside `framer-motion`. Two copies
of the same library; bundle bloat (~70 KB extra).

**B)** Set Bun workspace alias mapping `motion` → `framer-motion`.
Cleanest, no bundle bloat. Risk: Motion-React's newest exports may
not back-port to framer-motion 12 (e.g. v13-only APIs). The
wrapper only uses `motion`, `useAnimation`, types — all present in
framer-motion 12.

**Pick (B) — workspace alias.** Add to `packages/web/vite.config.ts`
`resolve.alias`:
```
{ find: "motion/react", replacement: "framer-motion" }
{ find: "motion",       replacement: "framer-motion" }
```

If the wrapper later breaks on an exclusive Motion v13 API, switch
to (A); revisit at that point.

### Decision 2: Curated 15-icon subset, not full sweep

The scope sweeps Groups A + B (15 icons). Group C (11 icons) stays
on lucide. Rationale: animate-ui icons cost ~3-5 KB each (wrapper
+ icon component) and bundle bloat compounds. The 15 chosen are
the highest-frequency user interactions on the surface; the 11
excluded are passive markers inside primitives. Scope boundary:
this is a UI polish change, not a dependency standardisation.

### Decision 3: Hover-only trigger by default

Each swapped call site SHALL pass `animateOnHover` to the icon
component. NOT `animateOnView` (would animate on scroll into the
viewport, visually noisy with the 3-pane workspace) and NOT
`animateOnTap` (would compete with button click handlers' own
visual feedback).

Exception: `Loader2` (which becomes `Spinner` in animate-ui naming,
imported as `Loader`) SHALL use `animate="loop"` because spinners
loop indefinitely by definition.

### Decision 4: Centralise install location

All animate-ui icons land in
`packages/web/src/components/animate-ui/icons/` — a new directory.
The wrapper file is `icon.tsx`, individual icons match their
kebab-cased names (e.g. `arrow-left.tsx`, `refresh-cw.tsx`). Group
C icons keep importing from `lucide-react` directly with no path
changes.

### Decision 5: Spec policy lives in ui-design-system

The icon-library policy belongs in `ui-design-system` because that
spec already governs the framer-motion / magicui / animate-ui split.
Add ONE new requirement clarifying the icon-policy split (lucide
for structural / passive, animate-ui for action / hero). This is
an ADD, not a MODIFY of the existing animation library policy.

## Implementation Contract

**Behavior**

- After this change ships, hovering any of the 15 swapped icons
  SHALL trigger a path-draw or scale animation (the wrapper's
  default per-icon preset). On mouse leave the animation SHALL
  finish gracefully — no abrupt reset.
- `prefers-reduced-motion: reduce` SHALL render every swapped icon
  as a static glyph identical to the current lucide render.
- The 11 Group C icons SHALL continue importing from `lucide-react`
  unchanged.
- `bun test` SHALL show 321 / 0 fail after the swap (no selector
  rewrites needed because `<svg>` queries still resolve).

**Data shapes (TypeScript)**

```ts
// Wrapper API (already shipped by the registry)
type StaticAnimations = "path" | "path-loop";
type Trigger = boolean | StaticAnimations | string;
type DefaultIconProps = {
  animate?: Trigger;
  animateOnHover?: Trigger;
  animateOnTap?: Trigger;
  animateOnView?: Trigger;
  className?: string;
};
```

**Failure modes**

- If the `motion` alias misroutes and the wrapper imports fail at
  build time, the change SHALL fall back to installing the `motion`
  npm package alongside `framer-motion` (Decision 1 option A).
- If any of the 15 registry icon installs returns a 404 (icon name
  mismatch with lucide's kebab-case), the implementation SHALL log
  the missing icon and either find a different name on the registry
  or revert that single icon to lucide-react.

**Acceptance criteria**

- `bun test` 321 / 0 fail
- `bunx tsc --noEmit` 0 errors
- `bunx oxlint` 0 warnings, 0 errors
- `bun run build` succeeds
- All 14 call sites under `Affected code → Modified` no longer
  import the relevant icon names from `lucide-react`
- 15 new icon component files exist under
  `packages/web/src/components/animate-ui/icons/`
- `packages/web/src/components/animate-ui/icons/icon.tsx` (the
  wrapper) exists and is the only file that imports from `motion/react`

**Scope boundaries (in / out)**

- In: 15 icon files + wrapper + 2 helpers, 14 call-site imports,
  1 vite alias config block, 1 spec ADD requirement.
- Out: Group C icons, theme-toggle internals, shadcn primitives
  (select / dropdown-menu / tabs), the inline NavBar logo SVG,
  any other lucide use NOT in the 15-icon list, ANY backend /
  auth / route-tree change.
