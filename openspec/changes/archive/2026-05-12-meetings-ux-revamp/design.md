## Context

The web package has 13 spec capabilities and ~60 component files post
`animate-ui-icons-swap`. Sean's review session surfaced six discrete
visual / interaction issues; this change ships five of them (the
sixth — MetadataCard right-column empty space — was deferred per
Sean's call). All five share a single user surface (the meetings
flow: list → detail / new / calendar) and pull from the same
primitive set (Pane, Card, Badge, Button, Tabs).

Existing constraints to respect:
- Primary palette stays purple (light hue 280) / orange (dark hue 50).
- The icon-library policy from `animate-ui-icons-swap` is law: 10
  icons through animate-ui, 16 through lucide. New buttons added in
  this change SHOULD reuse existing icons rather than introducing new
  ones.
- The 1600px max-width container from the post-archive UI overhaul
  polish is the authoritative outer width.
- Tests run through happy-dom; per-second re-render side effects
  hurt the harness — avoid live timers.
- React Query caches the meetings list under
  `meetingsListQueryOptions().queryKey`; the prev/next nav uses this
  cache, NOT a fresh fetch.

## Goals

- Add `--color-secondary` (and `-foreground` companion) keyed to
  oklch hue 195 in both light and dark theme blocks of `index.css`,
  and route shadcn `Button variant="secondary"` through the new
  token without touching other variants.
- Replace the standalone BackLink row on /meetings/$id with a
  3-button group inside the MetadataCard header
  (`prev` / `BackLink` / `next`), where prev / next derive from the
  React Query list cache sorted by `scheduled_start_at ASC NULLS
  LAST`. Disabled when no neighbour or cache miss.
- Mount a shared `<MeetingsViewTabs>` component on both /meetings
  and /meetings/calendar with labels Kanban / 行事曆.
- Pass `?from=calendar` on the calendar's "新會議" button; NewMeeting
  reads it to send post-create + Cancel back to /meetings/calendar.
- Replace the auto-fill grid on /meetings with a 3-column Kanban
  bucketed by date: 即將到來 / 未來 / 已結束. Cards keep their
  current shape; columns scroll vertically.

## Non-Goals

- NOT changing the meeting status state machine.
- NOT adding drag-to-change-status to the Kanban.
- NOT filling the MetadataCard right column when CaptureIndicator
  is hidden (Sean explicitly deferred this; the right column stays
  empty in the non-in_progress phase for this change).
- NOT touching tactical-advisor, playbook, summary, or transcript
  panes inside the detail page.
- NOT moving any icon between lucide / animate-ui beyond what new
  call sites need (and the existing policy still governs).
- NOT touching backend / auth / route-tree.

## Decisions

### Decision 1: Secondary colour as a separate token, not a primary alias

The new `--color-secondary` SHALL be defined as its own oklch value
(hue 195) in both theme blocks, NOT as a `var(--color-primary)`
alias and NOT as a `var(--color-surface-2)` alias. The pre-change
binding (`var(--color-surface-2)`) gets removed; any UI that relied
on the surface-tone behaviour MUST switch to `bg-(--color-muted)` or
`bg-(--color-surface-2)` directly. Light value: `oklch(0.62 0.12 195)`,
foreground `oklch(1 0 0)`. Dark value: `oklch(0.7 0.13 195)`,
foreground `oklch(0.14 0.012 var(--primary-hue-dark))`.

### Decision 2: Prev/next nav uses cache-only lookup

The `<MeetingPrevNextNav>` component reads the React Query cache via
`queryClient.getQueryData(meetingsListQueryOptions().queryKey)`. It
does NOT trigger a new fetch. Rationale:
- Pages that hit the detail route via list link already have the
  cache primed.
- A deep-link or bookmark entry would force a fetch otherwise; that
  fetch can race with the primary detail query and surface confusing
  loading states.
- Disabled-when-no-cache is honest: there's no neighbour we can
  guarantee without another round trip.

The sort is applied client-side in the component:

```ts
function sortKey(m: Meeting): string {
  // scheduled_start_at first (ASC), then created_at (DESC) tiebreak
  return m.scheduled_start_at ?? `~${m.created_at}`;
}
const sorted = [...meetings].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
```

The `~` prefix exploits ASCII ordering — `~` is greater than every
ISO-8601 digit, so undated meetings sort to the end. Inside that
tail, newer `created_at` floats up first because we compare the
ISO timestamp portion lexicographically (later ISO timestamps >
earlier ones).

### Decision 3: Date-bucket helper lives in lib, not the Kanban component

`getMeetingDateBucket(meeting, now)` SHALL live in
`packages/web/src/lib/meetings-bucket.ts` so unit tests can drive
it directly with frozen `now` values. The Kanban component just
calls the helper and groups; the bucket logic is pure.

Bucket boundaries (all comparisons against `now`):

- **upcoming** ("即將到來"):
  - `status === "in_progress"`, OR
  - `status === "scheduled"` AND `scheduled_start_at` ∈
    `[startOfToday, startOfToday + 7d)`
- **future** ("未來"):
  - `status === "scheduled"` AND `scheduled_start_at >=
    startOfToday + 7d`, OR
  - `status === "scheduled"` AND `scheduled_start_at` is null
- **past** ("已結束"):
  - `status === "completed"`, OR
  - `status === "scheduled"` AND `scheduled_start_at <
    startOfToday`

`startOfToday` SHALL be computed in the user's local timezone
(`new Date(now.getFullYear(), now.getMonth(), now.getDate())`).
This means the bucket boundary shifts at midnight local time.

### Decision 4: from=calendar redirect via TanStack Router search

NewMeeting consumes the optional `from` search param via TanStack
Router's `useSearch({ strict: false })`. Allowed value: `"calendar"`.
Any other value (or absence) defaults to /meetings/$id post-create
and /meetings on cancel.

```ts
const search = useSearch({ strict: false }) as { from?: string };
const cameFromCalendar = search.from === "calendar";
const cancelTo = cameFromCalendar ? "/meetings/calendar" : "/meetings";
const successTo = cameFromCalendar
  ? "/meetings/calendar"
  : { to: "/meetings/$id", params: { id: created.id } };
```

The calendar's "新會議" Link sets the search param via TanStack
Router's typed `to` + `search` props:
`<Link to="/meetings/new" search={{ from: "calendar" }}>`.

### Decision 5: MeetingsViewTabs uses radix Tabs in `controlled` mode

The shared tabs component owns the radix Tabs root with `value` set
from a prop and `onValueChange` calling `useNavigate()`. Both pages
pass their current value (`"kanban"` on /meetings, `"calendar"` on
/meetings/calendar) and ignore the onChange callback's value
parameter — the navigation is a one-way door per click.

This avoids needing useState in two places and ensures the URL is
the single source of truth.

### Decision 6: Kanban columns are equal-width with min-width caps

`<MeetingsKanban>` uses `display: grid; grid-template-columns:
repeat(3, minmax(280px, 1fr))` so each column is at least 280px
wide (card width) but expands to consume available space evenly.
Inside each column the content list uses `overflow-y: auto` with a
max height of `calc(100dvh - 280px)` (NavBar 56 + tab bar ~40 +
page padding + column header ~50 + outer breathing room).

## Implementation Contract

**Behavior**

- After this change ships, the meetings flow SHALL render with:
  - Buttons of `variant="secondary"` rendering teal (hue 195) in
    both themes, NOT grey.
  - The /meetings/$id page top-most content row showing
    `[← prev] 返回列表 [next →]` with prev / next disabled when
    no neighbour exists.
  - The /meetings page rendering 3 Kanban columns (即將到來 / 未來
    / 已結束) instead of an auto-fill grid.
  - The /meetings AND /meetings/calendar pages each rendering a
    Kanban / 行事曆 tab bar; clicking the inactive tab navigates.
  - The /meetings/calendar "新會議" link landing on /meetings/new
    with `?from=calendar`; submit / cancel both routing back to
    /meetings/calendar.
  - The MetadataCard right column on /meetings/$id stays empty
    when CaptureIndicator is hidden — no plan block, no timer,
    no fill (deferred to a future change).

**Data shapes (TypeScript)**

```ts
export type MeetingDateBucket = "upcoming" | "future" | "past";

export function getMeetingDateBucket(
  m: Pick<Meeting, "status" | "scheduled_start_at">,
  now: Date,
): MeetingDateBucket;

export interface MeetingsViewTabsProps {
  value: "kanban" | "calendar";
}

export interface MeetingPrevNextNavProps {
  currentId: string;
}
```

**Failure modes**

- If the React Query list cache is empty when MeetingPrevNextNav
  mounts, both arrows render disabled with a tooltip "從會議列表進入
  以啟用前後切換". No fetch is triggered.
- If the date-bucket helper receives an invalid `scheduled_start_at`
  (parse error), the meeting falls into the "已結束" bucket as a
  safe default and a console.warn is emitted in dev only.

**Acceptance criteria**

- `bun test` 337+ / 0 fail (current is 337; this change adds ~10
  new test cases, expecting 347+ pass)
- `bunx tsc --noEmit` 0 errors
- `bunx oxlint` 0 warnings, 0 errors
- `bun run build` succeeds
- 3 new components mount without throwing in their dedicated test
  files: MeetingsViewTabs, MeetingsKanban, MeetingPrevNextNav
- `getMeetingDateBucket` covers all 3 buckets + null
  `scheduled_start_at` + `status === "in_progress"` + overdue
  scheduled meeting in its unit test
- The 4 spec deltas land cleanly through the archive flow

**Scope boundaries (in / out)**

- In: secondary token, MetadataCard nav group (BackLink +
  prev/next), shared MeetingsViewTabs, from=calendar redirect,
  date-bucket Kanban + helper, 3 new component tests + 1 helper
  test, 4 spec ADD requirements.
- Out: drag-to-change-status, live timers, MetadataCard right-column
  fill (any kind), backend changes, meeting status state machine,
  NavBar layout, tactical-advisor / playbook / summary / transcript
  panes, ANY change to the icon policy beyond the existing 10-icon
  animate-ui set.
