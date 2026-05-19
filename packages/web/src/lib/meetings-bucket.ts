/**
 * meetings-bucket — slice-15 task 7.1 rewrite.
 *
 * Pure helper that maps a meeting onto one of three Kanban columns
 * keyed off lifecycle state. Replaces the older 7-day time-window
 * rules from meetings-ux-revamp.
 *
 *   completed       ("已結束"):   status === "in_progress" || "completed"
 *                                 (any meeting whose recording session
 *                                 has been started, regardless of the
 *                                 originally-scheduled time)
 *   upcoming        ("未來"):     status === "scheduled" && scheduled_start_at >= now
 *   needs_recording ("待補錄"):   status === "scheduled" && scheduled_start_at < now
 *                                 (the scheduled time has passed but no
 *                                 recording was started — needs follow-up)
 *
 * Invalid scheduled_start_at strings fall into needs_recording as a
 * safe default and emit a dev-only console.warn so the malformed row
 * gets the user's attention instead of disappearing into completed.
 */

import type { Meeting, MeetingBucket } from "./meetings-api";

/** Legacy alias kept for callsites that still import the old name. */
export type MeetingDateBucket = MeetingBucket;

/**
 * Resolve a meeting's bucket — prefers the backend-supplied `bucket` field
 * (authoritative since the schema added a `computed_field`), falls back to
 * the client-side compute for legacy fixtures / responses that pre-date
 * the bucket field.
 */
export function resolveMeetingBucket(
  m: Pick<Meeting, "status" | "scheduled_start_at" | "bucket">,
  now: Date = new Date(),
): MeetingBucket {
  return m.bucket ?? getMeetingDateBucket(m, now);
}

export function getMeetingDateBucket(
  m: Pick<Meeting, "status" | "scheduled_start_at">,
  now: Date,
): MeetingDateBucket {
  if (m.status === "in_progress" || m.status === "completed") {
    return "completed";
  }

  const scheduledAt = new Date(m.scheduled_start_at);
  if (Number.isNaN(scheduledAt.getTime())) {
    if (
      typeof import.meta !== "undefined" &&
      (import.meta as { env?: { DEV?: boolean } }).env?.DEV
    ) {
      // eslint-disable-next-line no-console
      console.warn(
        `[meetings-bucket] invalid scheduled_start_at: ${m.scheduled_start_at} → bucketing as needs_recording`,
      );
    }
    return "needs_recording";
  }

  if (scheduledAt >= now) return "upcoming";
  return "needs_recording";
}
