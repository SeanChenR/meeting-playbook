/**
 * meetings-bucket — slice-15 task 7.2 rewrite.
 *
 * New 3-column rules (replaces the 7-day time-window rules from
 * meetings-ux-revamp). Bucket assignment now keys off lifecycle state:
 *
 *   completed       ("已結束"):   status === "in_progress" || "completed"
 *   upcoming        ("未來"):     status === "scheduled" && scheduled_start_at >= now
 *   needs_recording ("待補錄"):   status === "scheduled" && scheduled_start_at < now,
 *                                 OR scheduled with invalid ISO (safe default)
 *
 * Frozen `now` lets the test pin the boundary without mocking Date.
 */

import { describe, expect, test } from "bun:test";
import { getMeetingDateBucket, type MeetingDateBucket } from "./meetings-bucket";

const _NOW = new Date("2026-05-12T10:00:00Z");

interface SampleInput {
  status: "scheduled" | "in_progress" | "completed";
  scheduled_start_at: string;
}

const _bucket = (m: SampleInput): MeetingDateBucket => getMeetingDateBucket(m, _NOW);

describe("getMeetingDateBucket — new 3-bucket rules (slice-15 task 7.2)", () => {
  test("(a) in_progress with past scheduled → completed", () => {
    expect(_bucket({ status: "in_progress", scheduled_start_at: "2026-04-01T09:00:00Z" })).toBe(
      "completed",
    );
  });

  test("(b) completed with past scheduled → completed", () => {
    expect(_bucket({ status: "completed", scheduled_start_at: "2026-04-15T10:00:00Z" })).toBe(
      "completed",
    );
  });

  test("(c) scheduled with scheduled_start_at >= now → upcoming", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-25T15:00:00Z" })).toBe(
      "upcoming",
    );
  });

  test("(d) scheduled with scheduled_start_at < now → needs_recording (overdue)", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "2026-05-01T15:00:00Z" })).toBe(
      "needs_recording",
    );
  });

  test("(e) boundary scheduled_start_at === now → upcoming (half-open future)", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: _NOW.toISOString() })).toBe(
      "upcoming",
    );
  });

  test("(f) invalid ISO string → needs_recording (safe default)", () => {
    expect(_bucket({ status: "scheduled", scheduled_start_at: "not-a-date" })).toBe(
      "needs_recording",
    );
  });
});
