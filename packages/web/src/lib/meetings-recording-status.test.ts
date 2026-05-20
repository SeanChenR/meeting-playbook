/**
 * Recording status resolver — covers refactor task 12.7.
 *
 * Five states / cases:
 *   - recordings_available === true                       → available (green)
 *   - bucket === "needs_recording"                        → pending (orange)
 *   - bucket === "completed" && !recordings_available     → expired (mauve)
 *   - bucket === "upcoming"                               → hidden (no indicator)
 *   - colorVar/i18nKey mapping is correct per state
 */

import { describe, expect, test } from "bun:test";
import type { MeetingDetail } from "./meetings-api";
import { recordingStatusVisual, resolveRecordingStatus } from "./meetings-recording-status";

const FAR_PAST = "2020-01-01T00:00:00Z";
const FAR_FUTURE = "2099-12-31T00:00:00Z";

function _makeMeeting(overrides: Partial<MeetingDetail>): MeetingDetail {
  return {
    id: "m_test",
    user_id: "u",
    title: "Test meeting",
    counterparty_display_name: "對方",
    me_display_name: "我",
    status: "scheduled",
    asr_provider: "whisper",
    calendar_event_id: null,
    created_at: FAR_PAST,
    started_at: null,
    ended_at: null,
    scheduled_start_at: FAR_FUTURE,
    scheduled_end_at: FAR_FUTURE,
    recordings_available: false,
    rerun_asr_pending: false,
    ...overrides,
  } as MeetingDetail;
}

describe("resolveRecordingStatus", () => {
  test("(a) recordings_available=true → available", () => {
    const m = _makeMeeting({ recordings_available: true, status: "completed" });
    expect(resolveRecordingStatus(m)).toBe("available");
  });

  test("(b) bucket=needs_recording → pending", () => {
    // needs_recording: scheduled time has passed, status still scheduled, no recordings
    const m = _makeMeeting({
      status: "scheduled",
      scheduled_start_at: FAR_PAST,
      scheduled_end_at: FAR_PAST,
      recordings_available: false,
    });
    expect(resolveRecordingStatus(m)).toBe("pending");
  });

  test("(c) bucket=completed && !recordings_available → expired", () => {
    const m = _makeMeeting({ status: "completed", recordings_available: false });
    expect(resolveRecordingStatus(m)).toBe("expired");
  });

  test("(d) bucket=upcoming → scheduled (claude-design follow-up: header pill always renders)", () => {
    const m = _makeMeeting({
      status: "scheduled",
      scheduled_start_at: FAR_FUTURE,
      scheduled_end_at: FAR_FUTURE,
      recordings_available: false,
    });
    expect(resolveRecordingStatus(m)).toBe("scheduled");
  });
});

describe("recordingStatusVisual", () => {
  test("(e1) available → --color-success / recordingAvailable key", () => {
    expect(recordingStatusVisual("available")).toEqual({
      status: "available",
      colorVar: "--color-success",
      i18nKey: "meetings.detail.recordingAvailable",
    });
  });

  test("(e2) pending → --color-warning / recordingPending key", () => {
    expect(recordingStatusVisual("pending")).toEqual({
      status: "pending",
      colorVar: "--color-warning",
      i18nKey: "meetings.detail.recordingPending",
    });
  });

  test("(e3) expired → --color-accent / recordingExpired key", () => {
    expect(recordingStatusVisual("expired")).toEqual({
      status: "expired",
      colorVar: "--color-accent",
      i18nKey: "meetings.detail.recordingExpired",
    });
  });

  test("(e4) hidden → empty colorVar / empty i18nKey", () => {
    expect(recordingStatusVisual("hidden")).toEqual({
      status: "hidden",
      colorVar: "",
      i18nKey: "",
    });
  });

  test("(e5) no grey tokens used in any state", () => {
    const states: Array<"available" | "pending" | "expired" | "hidden"> = [
      "available",
      "pending",
      "expired",
      "hidden",
    ];
    for (const s of states) {
      const v = recordingStatusVisual(s);
      expect(v.colorVar).not.toContain("muted-foreground");
      expect(v.colorVar).not.toContain("surface-3");
    }
  });
});
