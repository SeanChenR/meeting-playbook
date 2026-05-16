/**
 * Dashboard stats API client — Sean revision 3.
 *
 * Wraps `GET /api/meetings/stats?month=YYYY-MM`. Defaults to the current
 * Asia/Taipei month when `month` is omitted. Errors normalize to
 * `StatsApiError` with the legacy `stats.invalid_range` code so the
 * frontend i18n table still resolves.
 */

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

export interface TopCounterpartyBucket {
  display_name: string;
  count: number;
}

export interface TagBucket {
  tag: string;
  count: number;
}

export interface DailyBucket {
  day: number; // 1..31
  count: number;
}

export interface HourBucket {
  hour: number; // 0..23
  count: number;
}

export interface DashboardStats {
  month: string; // YYYY-MM
  prev_month: string; // YYYY-MM
  meeting_count: number;
  prev_month_meeting_count: number;
  avg_duration_seconds: number | null;
  total_duration_seconds: number;
  top_counterparties: TopCounterpartyBucket[];
  daily_trend: DailyBucket[];
  hour_distribution: HourBucket[];
  tag_distribution: TagBucket[];
}

export class StatsApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<StatsApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    /* keep defaults */
  }
  return new StatsApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function fetchStats(month?: string): Promise<DashboardStats> {
  const qs = month ? `?month=${encodeURIComponent(month)}` : "";
  const resp = await fetch(`/api/meetings/stats${qs}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as DashboardStats;
}

export function statsQueryOptions(
  month: string | undefined,
): UseQueryOptions<DashboardStats, StatsApiError> {
  return {
    queryKey: ["meetings", "stats", month ?? "current"],
    queryFn: () => fetchStats(month),
  };
}

export function useStatsQuery(month?: string) {
  return useQuery(statsQueryOptions(month));
}

/** Format an `YYYY-MM` string into `2026年5月` / `May 2026` for headers. */
export function formatMonthLabel(month: string, locale: string): string {
  const [yearStr, monthStr] = month.split("-");
  const year = Number.parseInt(yearStr ?? "", 10);
  const monthNum = Number.parseInt(monthStr ?? "", 10);
  if (!Number.isFinite(year) || !Number.isFinite(monthNum)) return month;
  const date = new Date(Date.UTC(year, monthNum - 1, 1));
  return date.toLocaleDateString(locale, { year: "numeric", month: "long" });
}

/** Shift an `YYYY-MM` string by `delta` months (handles year roll-over). */
export function shiftMonth(month: string, delta: number): string {
  const [yearStr, monthStr] = month.split("-");
  const year = Number.parseInt(yearStr ?? "", 10);
  const monthNum = Number.parseInt(monthStr ?? "", 10);
  const totalMonths = (year - 1) * 12 + (monthNum - 1) + delta;
  const nextYear = Math.floor(totalMonths / 12) + 1;
  const nextMonth = (totalMonths % 12) + 1;
  return `${String(nextYear).padStart(4, "0")}-${String(nextMonth).padStart(2, "0")}`;
}

/** Format the current Asia/Taipei month as `YYYY-MM`. */
export function currentMonth(): string {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
  });
  // `en-CA` produces `YYYY-MM` reliably.
  return fmt.format(new Date());
}
