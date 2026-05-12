## Summary

Revamp the meetings list / calendar / detail surfaces to address Sean's
post-archive UX feedback: add a real secondary brand colour (teal hue
195), unify the card / calendar tab bar across both views, fix the
calendar-origin redirect, add prev/next meeting navigation alongside
the BackLink, and replace the auto-fill list grid with a 3-column
Kanban grouped by date (即將到來 / 未來 / 已結束).

## Motivation

After `ui-overhaul-claude-design` and `animate-ui-icons-swap` shipped,
Sean reviewed the rendered surface and flagged five issues this
change addresses (a sixth, the empty space in the MetadataCard right
column when the session is not in_progress, was discussed but
deliberately deferred — see Non-Goals):

1. The palette has no real secondary brand colour — `--color-secondary`
   currently aliases `--color-surface-2` (a neutral grey). Any UI that
   needs to signal "secondary action" without leaning on neutral
   surface has nothing to use.
2. The standalone BackLink at the top of /meetings/$id sits on its
   own row with generous vertical padding above and below. The space
   feels lonely and the user has no way to flip to the previous or
   next meeting without going back to the list.
3. /meetings has a Tabs row (卡片 / 日曆) but /meetings/calendar does
   not — once the user lands on the calendar they cannot toggle back
   without using the browser back button or the NavBar logo.
4. Creating or cancelling a meeting from the calendar redirects to
   /meetings (card list), not back to /meetings/calendar — breaking
   the user's mental flow.
5. The /meetings list grid is described as "醜" — a flat auto-fill
   of identical cards with no semantic grouping. A Kanban board
   grouped by date (即將到來 / 未來 / 已結束) would give the page
   meaning at a glance and match how Sean naturally thinks about
   his meeting backlog.

## Proposed Solution

**Secondary colour token** — add `--color-secondary` and
`--color-secondary-foreground` keyed to oklch hue 195 (teal/cyan)
in both light + dark theme blocks. Wire `Button variant="secondary"`
to use the new token. This is purely a new colour slot, not a palette
redesign — primary stays purple/orange, accent stays = primary.

**BackLink + prev/next nav** — the BackLink moves OUT of the
standalone row and INTO a new top-row group: `[< prev] [BackLink]
[next >]`. The two arrow buttons navigate to the previous / next
meeting sorted by `scheduled_start_at` ASC NULLS LAST (so meetings
with a date come first; undated meetings sort to the end by
`created_at` DESC). Buttons use React Query's existing list cache
to find neighbour IDs; if the cache misses (deep-link entry without
visiting the list first), the buttons render disabled.

**Shared MeetingsViewTabs component** — extract a `<MeetingsViewTabs
value="kanban" | "calendar" />` component using the labels
**Kanban** / **行事曆**. Mount on both /meetings and
/meetings/calendar; clicking the inactive tab navigates to that
route. The list page's existing inline Tabs are removed.

**from=calendar redirect** — `<Link to="/meetings/new">` on the
calendar's "新會議" button passes `?from=calendar`. NewMeeting reads
the query and routes the post-create + Cancel actions back to
/meetings/calendar instead of /meetings/$id. The List page's "新會議"
link omits the query → keeps the current /meetings/$id navigation
behaviour.

**Date-bucket Kanban** — `<MeetingsKanban>` replaces the auto-fill
grid with three vertical columns keyed by `scheduled_start_at` and
`status`:

- **即將到來** — `scheduled_start_at` between today 00:00 and 7 days
  out, OR `status === "in_progress"` regardless of date
- **未來** — `scheduled_start_at` > 7 days out, OR no
  `scheduled_start_at` and `status === "scheduled"`
- **已結束** — `status === "completed"`, OR `scheduled_start_at`
  before today (overdue undelivered meetings dropped here so they
  stop cluttering the upcoming column)

Each column has a header (label + count badge), scrolls vertically
when overflowing, and shows an empty-state hint when zero meetings.
Cards keep the same shape (status bar, title, counterparty, time,
duration). Drag-to-reorder / drag-to-change-status is OUT of scope.

## Non-Goals

- NOT redesigning the entire colour palette — only adds the secondary
  slot. Primary stays purple/orange. Accent stays = primary.
- NOT changing the meeting status state machine
  (scheduled → in_progress → completed). Kanban columns are read-only
  groupings derived off `status` + `scheduled_start_at`.
- NOT adding drag-to-change-status to the Kanban — needs a PATCH
  endpoint + state-machine validation + WS notification, all out of
  scope. A separate change can layer it on top.
- NOT filling the MetadataCard right column when CaptureIndicator is
  hidden — Sean reviewed proposed solutions (plan block, timer,
  layout collapse) and chose to defer all of them. The right column
  stays empty in the non-in_progress phase for this change.
- NOT touching tactical-advisor / playbook / summary panes inside
  the detail page. The metadata + back-link work stays above the
  Workspace / Summary tab content.
- NOT moving icons inside shadcn primitives (those stay on lucide
  per the icon-library policy added in `animate-ui-icons-swap`).
- NOT adjusting NavBar layout further — the 1600px max-width inner
  wrapper from the post-archive UI overhaul polish stays.

## Alternatives Considered

- **Drag-and-drop Kanban**: rejected — forces backend PATCH +
  state-machine + concurrency reasoning that overruns the 15-task
  budget.
- **Status-based Kanban columns (scheduled / in_progress / completed)**:
  rejected per Sean's preference for date-based grouping; date
  matches how he naturally thinks about the backlog.
- **MetadataCard plan block / live timer / layout collapse**:
  considered as Q2 candidates; Sean rejected all and chose to defer
  the right-column-empty problem entirely (see Non-Goals).
- **Move BackLink into the global NavBar**: rejected because NavBar
  is shared by every protected route; pinning a meeting-specific
  BackLink there would either need conditional render logic or
  break the home page's visual rhythm.
- **referrer / sessionStorage for the calendar-origin redirect**:
  rejected — query param is the simplest, survives reload, and
  shows up in the URL so users can bookmark / share if they want.

## Impact

- Affected specs: `ui-design-system`, `meeting-management`,
  `meetings-calendar-view`, `meeting-detail-layout`
- Affected code:
  - New:
    - packages/web/src/components/meetings-view-tabs.tsx
    - packages/web/src/components/meetings-kanban.tsx
    - packages/web/src/components/meeting-prev-next-nav.tsx
    - packages/web/src/components/meetings-view-tabs.test.tsx
    - packages/web/src/components/meetings-kanban.test.tsx
    - packages/web/src/components/meeting-prev-next-nav.test.tsx
    - packages/web/src/lib/meetings-bucket.ts (date-bucket helper)
    - packages/web/src/lib/meetings-bucket.test.ts
  - Modified:
    - packages/web/src/index.css (new --color-secondary tokens, both themes)
    - packages/web/src/components/metadata-card.tsx (BackLink + prev/next slot)
    - packages/web/src/routes/meetings/list.tsx (replace grid with Kanban + use shared Tabs)
    - packages/web/src/routes/meetings/calendar.tsx (mount shared Tabs + pass ?from=calendar on 新會議)
    - packages/web/src/routes/meetings/new.tsx (read ?from=calendar; redirect & cancel routing)
    - packages/web/src/routes/meetings/detail.tsx (drop standalone BackLink row; embed nav group in MetadataCard)
    - openspec/specs/ui-design-system/spec.md (secondary token requirement ADD)
    - openspec/specs/meeting-management/spec.md (Kanban grouping requirement ADD)
    - openspec/specs/meetings-calendar-view/spec.md (shared tabs + from=calendar redirect ADD)
    - openspec/specs/meeting-detail-layout/spec.md (prev/next nav ADD)
  - Removed: (none)
