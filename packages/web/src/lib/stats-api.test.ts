/**
 * `stats-api` client unit tests — Sean revision 3 (month-arrow picker).
 *
 * Covers:
 *   - happy path returns the typed DashboardStats body (new shape)
 *   - 400 `stats.invalid_range` envelope is mapped to `StatsApiError.errorCode`
 *   - request URL carries the `month` query param
 *   - omitting `month` issues the bare `/api/meetings/stats` URL
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { fetchStats, shiftMonth, StatsApiError } from "./stats-api";

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
});

describe("fetchStats", () => {
  test("issues GET /api/meetings/stats with the month query param", async () => {
    let capturedUrl = "";
    globalThis.fetch = (async (url: string) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          month: "2026-05",
          prev_month: "2026-04",
          meeting_count: 0,
          prev_month_meeting_count: 0,
          avg_duration_seconds: null,
          total_duration_seconds: 0,
          top_counterparties: [],
          daily_trend: [{ day: 1, count: 0 }],
          hour_distribution: [{ hour: 0, count: 0 }],
          tag_distribution: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const stats = await fetchStats("2026-05");

    expect(capturedUrl).toBe("/api/meetings/stats?month=2026-05");
    expect(stats.month).toBe("2026-05");
    expect(stats.prev_month).toBe("2026-04");
    expect(stats.meeting_count).toBe(0);
    expect(stats.daily_trend).toHaveLength(1);
    expect(stats.hour_distribution).toHaveLength(1);
  });

  test("omitting month issues the bare /api/meetings/stats URL", async () => {
    let capturedUrl = "";
    globalThis.fetch = (async (url: string) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          month: "2026-05",
          prev_month: "2026-04",
          meeting_count: 0,
          prev_month_meeting_count: 0,
          avg_duration_seconds: null,
          total_duration_seconds: 0,
          top_counterparties: [],
          daily_trend: [],
          hour_distribution: [],
          tag_distribution: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    await fetchStats();
    expect(capturedUrl).toBe("/api/meetings/stats");
  });

  test("decodes 400 stats.invalid_range into StatsApiError.errorCode", async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          error_code: "stats.invalid_range",
          message: "Invalid month: 13",
        }),
        { status: 400, headers: { "content-type": "application/json" } },
      )) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await fetchStats("2026-13");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(StatsApiError);
    const err = thrown as StatsApiError;
    expect(err.status).toBe(400);
    expect(err.errorCode).toBe("stats.invalid_range");
  });
});

describe("shiftMonth", () => {
  test("steps forward across a year boundary", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });
  test("steps backward across a year boundary", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
  });
  test("multi-month steps add up", () => {
    expect(shiftMonth("2026-05", -6)).toBe("2025-11");
  });
});
