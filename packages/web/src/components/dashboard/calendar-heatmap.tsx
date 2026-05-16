/**
 * CalendarHeatmap — Sean revision 3.
 *
 * GitHub-style activity grid showing meeting density per day across the
 * selected month. The grid lays out one cell per day-of-month positioned
 * under the matching weekday column; empty leading / trailing cells
 * preserve weekday alignment.
 *
 * Cell intensity scales linearly from 0 to `max(daily_trend.count)`. The
 * `var(--color-primary)` token drives the active colour so dark / light
 * theme swaps propagate via CSS.
 */

import { useTranslation } from "react-i18next";
import type { DashboardStats } from "../../lib/stats-api";
import { GradientCardFrame } from "../magicui/gradient-card-frame";

interface Props {
  stats: DashboardStats;
}

interface Cell {
  day: number | null; // null for leading / trailing padding
  count: number;
}

function _buildGrid(month: string, dailyByDay: Map<number, number>, totalDays: number): Cell[] {
  const [yearStr, monthStr] = month.split("-");
  const year = Number.parseInt(yearStr ?? "", 10);
  const monthNum = Number.parseInt(monthStr ?? "", 10);
  if (!Number.isFinite(year) || !Number.isFinite(monthNum)) return [];
  // JS getDay(): 0=Sun..6=Sat. Use UTC so the day-of-week math is locale-free.
  const firstDow = new Date(Date.UTC(year, monthNum - 1, 1)).getUTCDay();
  const cells: Cell[] = [];
  for (let i = 0; i < firstDow; i++) cells.push({ day: null, count: 0 });
  for (let d = 1; d <= totalDays; d++) cells.push({ day: d, count: dailyByDay.get(d) ?? 0 });
  // Pad trailing so the grid ends on a Saturday boundary (cleaner visual).
  while (cells.length % 7 !== 0) cells.push({ day: null, count: 0 });
  return cells;
}

export function CalendarHeatmap({ stats }: Props) {
  const { t } = useTranslation();
  const dailyByDay = new Map(stats.daily_trend.map((b) => [b.day, b.count] as const));
  const totalDays = stats.daily_trend.length || 31;
  const cells = _buildGrid(stats.month, dailyByDay, totalDays);
  const maxCount = Math.max(0, ...stats.daily_trend.map((b) => b.count));

  return (
    <GradientCardFrame
      data-testid="dashboard-chart-calendar-heatmap"
      disableHover
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
      className="h-full"
      bodyClassName="h-full"
    >
      <div className="flex h-full flex-col rounded-[inherit] p-5">
        <header className="flex items-baseline justify-between pb-3">
          <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
            {t("dashboard.charts.calendar_heatmap")}
          </h3>
        </header>
        {maxCount === 0 ? (
          <p className="py-10 text-center text-xs text-(--color-muted-foreground)">
            {t("dashboard.empty")}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-7 gap-1 text-center text-[10px] text-(--color-muted-foreground)">
              {["S", "M", "T", "W", "T", "F", "S"].map((d, idx) => (
                <span key={`${d}-${idx}`}>{d}</span>
              ))}
            </div>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {cells.map((cell, idx) => {
                if (cell.day === null) {
                  return <div key={`pad-${idx}`} className="aspect-square rounded-sm" />;
                }
                const intensity = maxCount === 0 ? 0 : cell.count / maxCount;
                const bg =
                  cell.count === 0
                    ? "var(--color-muted)"
                    : `color-mix(in oklch, var(--color-primary) ${15 + Math.round(intensity * 70)}%, var(--color-card))`;
                return (
                  <div
                    key={`d-${cell.day}`}
                    data-testid={`dashboard-heatmap-day-${cell.day}`}
                    title={t("dashboard.charts.dayCellTitle", {
                      day: cell.day,
                      count: cell.count,
                    })}
                    className="flex aspect-square items-center justify-center rounded-sm text-[10px] text-(--color-muted-foreground) transition-colors hover:ring-1 hover:ring-(--color-primary)/40"
                    style={{ background: bg }}
                  >
                    {cell.day}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center justify-end gap-1.5 text-[10px] text-(--color-muted-foreground)">
              <span>{t("dashboard.charts.legendLow")}</span>
              {[0.1, 0.3, 0.5, 0.75, 1].map((level) => (
                <span
                  key={level}
                  className="size-3 rounded-sm"
                  style={{
                    background: `color-mix(in oklch, var(--color-primary) ${15 + Math.round(level * 70)}%, var(--color-card))`,
                  }}
                />
              ))}
              <span>{t("dashboard.charts.legendHigh")}</span>
            </div>
          </>
        )}
      </div>
    </GradientCardFrame>
  );
}
