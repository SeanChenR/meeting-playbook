/**
 * Resolve the visual recording status for a meeting.
 *
 * Derived purely from `meeting.recordings_available` + the bucket the meeting
 * falls into (upcoming / needs_recording / completed). No backend schema
 * change required.
 *
 * State precedence (in order, first match wins):
 *   1. `recordings_available === true`  → "available" (green)
 *   2. bucket === "needs_recording"     → "pending"   (orange)
 *   3. bucket === "completed"            → "expired"   (mauve)
 *   4. bucket === "upcoming"             → "hidden"    (no indicator)
 *
 * Grey tokens are intentionally NOT used — Sean rejected `--color-muted-foreground`
 * as too lifeless for any state. Past-tense uses accent (mauve), pending uses warning.
 */

import type { MeetingDetail } from "./meetings-api";
import { resolveMeetingBucket } from "./meetings-bucket";

export type RecordingStatus = "available" | "pending" | "expired" | "hidden";

export interface RecordingStatusVisual {
  status: RecordingStatus;
  /** CSS variable name for the dot colour. Empty when `status === "hidden"`. */
  colorVar: string;
  /** i18n key for the label, or empty when `status === "hidden"`. */
  i18nKey: string;
}

export function resolveRecordingStatus(meeting: MeetingDetail): RecordingStatus {
  if (meeting.recordings_available === true) return "available";
  const bucket = resolveMeetingBucket(meeting);
  if (bucket === "needs_recording") return "pending";
  if (bucket === "completed") return "expired";
  return "hidden";
}

export function recordingStatusVisual(status: RecordingStatus): RecordingStatusVisual {
  switch (status) {
    case "available":
      return {
        status,
        colorVar: "--color-success",
        i18nKey: "meetings.detail.recordingAvailable",
      };
    case "pending":
      return {
        status,
        colorVar: "--color-warning",
        i18nKey: "meetings.detail.recordingPending",
      };
    case "expired":
      return {
        status,
        colorVar: "--color-accent",
        i18nKey: "meetings.detail.recordingExpired",
      };
    case "hidden":
      return { status, colorVar: "", i18nKey: "" };
  }
}
