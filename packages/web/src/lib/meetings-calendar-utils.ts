/**
 * meetings-calendar-utils — pure helpers for the slice-07 calendar view.
 *
 * Two helpers:
 *   meetingToCalendarEvent — converts a meeting row to a react-big-calendar
 *     event object. Slice-15 made `scheduled_start_at` NOT NULL so this
 *     function no longer short-circuits to null; every meeting renders on
 *     the grid.
 *   statusToEventClassName — Tailwind classes by meeting status for
 *     react-big-calendar's eventPropGetter.
 *
 * Per design.md `Calendar view library: react-big-calendar Month/Week`.
 */

import type { Meeting } from "./meetings-api";

export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resource: Meeting;
}

export function meetingToCalendarEvent(meeting: Meeting): CalendarEvent {
  const start = new Date(meeting.scheduled_start_at);
  // Default end = start + 30min when scheduled_end_at is null (some Calendar
  // events arrive without an explicit end).
  const end = meeting.scheduled_end_at
    ? new Date(meeting.scheduled_end_at)
    : new Date(start.getTime() + 30 * 60_000);
  return {
    id: meeting.id,
    title: meeting.title,
    start,
    end,
    resource: meeting,
  };
}

export function statusToEventClassName(status: Meeting["status"]): string {
  // Tailwind utility classes for react-big-calendar's event pill.
  // Keep the palette aligned with the rest of the app: scheduled = primary
  // (blue-ish), in_progress = accent (green-ish), completed = muted.
  switch (status) {
    case "scheduled":
      return "rbc-event-scheduled bg-blue-500/80 border-blue-700 text-white";
    case "in_progress":
      return "rbc-event-in-progress bg-emerald-600/80 border-emerald-800 text-white";
    case "completed":
      return "rbc-event-completed bg-(--color-muted) border-(--color-border) text-(--color-muted-foreground)";
  }
}
