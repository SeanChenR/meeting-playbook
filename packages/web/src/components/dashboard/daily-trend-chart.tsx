/**
 * DailyTrendChart — Sean revision 3.
 *
 * Line chart of meeting counts per day-of-month. X axis spans 1..N (N =
 * days in the selected month). Backend zero-fills missing days so the
 * line stays continuous.
 */

import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardStats } from "../../lib/stats-api";
import { GradientCardFrame } from "../magicui/gradient-card-frame";

interface Props {
  stats: DashboardStats;
}

export function DailyTrendChart({ stats }: Props) {
  const { t } = useTranslation();
  const data = stats.daily_trend;
  const totalMeetings = data.reduce((sum, b) => sum + b.count, 0);

  return (
    <GradientCardFrame
      data-testid="dashboard-chart-daily-trend"
      disableHover
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
    >
      <div className="flex h-full flex-col rounded-[inherit] p-5">
        <header className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
            {t("dashboard.charts.daily_trend")}
          </h3>
          <span className="text-xs text-(--color-muted-foreground)">
            {t("dashboard.charts.totalLabel", { count: totalMeetings })}
          </span>
        </header>
        {totalMeetings === 0 ? (
          <p className="py-10 text-center text-xs text-(--color-muted-foreground)">
            {t("dashboard.empty")}
          </p>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="daily-trend-gradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="day"
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  interval={Math.max(1, Math.floor(data.length / 8))}
                />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
                <Tooltip
                  cursor={{ stroke: "var(--color-border)" }}
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                  labelFormatter={(v: number) => t("dashboard.charts.dayLabel", { day: v })}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  fill="url(#daily-trend-gradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </GradientCardFrame>
  );
}
