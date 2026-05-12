/**
 * meetings-bucket — slice meetings-ux-revamp Decision 3.
 *
 * Pure helper that maps a meeting onto one of three Kanban columns
 * based on its status and (optional) `scheduled_start_at`.
 *
 *   upcoming  ("即將到來"): in_progress regardless of date,
 *                          OR scheduled in [startOfToday, +7d)
 *   future    ("未來"):     scheduled >= startOfToday + 7d,
 *                          OR scheduled with no scheduled_start_at
 *   past      ("已結束"):   completed,
 *                          OR scheduled before startOfToday (overdue)
 *
 * `startOfToday` is computed in the user's local timezone — bucket
 * boundaries shift at midnight local time. Invalid date strings fall
 * into `past` as a safe default and emit a dev-only console.warn.
 */

import type { Meeting } from "./meetings-api";

export type MeetingDateBucket = "upcoming" | "future" | "past";

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function _startOfTodayLocal(now: Date): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export function getMeetingDateBucket(
  m: Pick<Meeting, "status" | "scheduled_start_at">,
  now: Date,
): MeetingDateBucket {
  if (m.status === "in_progress") return "upcoming";
  if (m.status === "completed") return "past";

  // status === "scheduled" from here.
  if (m.scheduled_start_at === null) return "future";

  const scheduledAt = new Date(m.scheduled_start_at);
  if (Number.isNaN(scheduledAt.getTime())) {
    if (
      typeof import.meta !== "undefined" &&
      (import.meta as { env?: { DEV?: boolean } }).env?.DEV
    ) {
      // eslint-disable-next-line no-console
      console.warn(
        `[meetings-bucket] invalid scheduled_start_at: ${m.scheduled_start_at} → bucketing as past`,
      );
    }
    return "past";
  }

  const startOfToday = _startOfTodayLocal(now);
  const sevenDaysOut = new Date(startOfToday.getTime() + SEVEN_DAYS_MS);

  if (scheduledAt < startOfToday) return "past";
  if (scheduledAt < sevenDaysOut) return "upcoming";
  return "future";
}
