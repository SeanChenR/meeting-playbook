/**
 * meetings-bucket — slice meetings-ux-revamp task 2.1.
 *
 * Pure helper that slots a meeting into one of three Kanban buckets:
 *   - upcoming  ("即將到來"): in_progress OR scheduled in [today, today+7d)
 *   - future    ("未來"):     scheduled >= today+7d OR scheduled w/o date
 *   - past      ("已結束"):   completed OR scheduled before today
 *
 * Frozen `now` lets the test pin the date boundary without mocking Date.
 */

import { describe, expect, test } from "bun:test";
import { getMeetingDateBucket, type MeetingDateBucket } from "./meetings-bucket";

const _NOW = new Date("2026-05-12T10:00:00");

interface SampleInput {
  status: "scheduled" | "in_progress" | "completed";
  scheduled_start_at: string | null;
}

const _bucket = (m: SampleInput): MeetingDateBucket => getMeetingDateBucket(m, _NOW);

describe("getMeetingDateBucket — Three-bucket distribution (spec scenario)", () => {
  test("a: in_progress regardless of date → upcoming", () => {
    expect(_bucket({ status: "in_progress", scheduled_start_at: "2026-04-01T09:00:00" })).toBe(
      "upcoming",
    );
  });

  test("b: scheduled tomorrow → upcoming", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-13T15:00:00" })).toBe(
      "upcoming",
    );
  });

  test("c: scheduled 13 days out → future", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-25T15:00:00" })).toBe(
      "future",
    );
  });

  test("d: scheduled with null date → future", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: null })).toBe("future");
  });

  test("e: completed → past", () => {
    expect(_bucket({ status: "completed", scheduled_start_at: "2026-04-15T10:00:00" })).toBe(
      "past",
    );
  });
});

describe("getMeetingDateBucket — edge cases", () => {
  test("Overdue scheduled meeting (status=scheduled, date < today) → past", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-01T15:00:00" })).toBe(
      "past",
    );
  });

  test("Boundary: scheduled exactly today midnight → upcoming", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-12T00:00:00" })).toBe(
      "upcoming",
    );
  });

  test("Boundary: scheduled exactly +7 days → future (window is half-open)", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-19T00:00:00" })).toBe(
      "future",
    );
  });

  test("Invalid scheduled_start_at string → past (safe default)", () => {
    expect(
      _bucket({
        status: "scheduled",
        scheduled_start_at: "not-a-date",
      }),
    ).toBe("past");
  });

  test("Completed with null scheduled_start_at → past", () => {
    expect(_bucket({ status: "completed", scheduled_start_at: null })).toBe("past");
  });
});
