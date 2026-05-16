/**
 * HourDistributionChart — Sean revision 3.
 *
 * Hour-of-day histogram showing when meetings tend to happen across the
 * selected month. X axis is `0..23` (Asia/Taipei). Backend zero-fills
 * every hour so the bars stay uniformly spaced even on sparse months.
 */

import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardStats } from "../../lib/stats-api";
import { GradientCardFrame } from "../magicui/gradient-card-frame";

interface Props {
  stats: DashboardStats;
}

export function HourDistributionChart({ stats }: Props) {
  const { t } = useTranslation();
  const data = stats.hour_distribution;
  const totalCount = data.reduce((sum, b) => sum + b.count, 0);

  return (
    <GradientCardFrame
      data-testid="dashboard-chart-hour-distribution"
      accent="var(--color-accent)"
      accentAlt="var(--color-primary)"
      className="h-full"
      bodyClassName="h-full"
    >
      <div className="flex h-full flex-col rounded-[inherit] p-5">
        <header className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
            {t("dashboard.charts.hour_distribution")}
          </h3>
        </header>
        {totalCount === 0 ? (
          <p className="flex-1 py-10 text-center text-xs text-(--color-muted-foreground)">
            {t("dashboard.empty")}
          </p>
        ) : (
          <div className="mt-4 min-h-[260px] flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="hour"
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  interval={2}
                  tickFormatter={(v: number) => `${v}`}
                />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: "var(--color-muted)" }}
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                  labelFormatter={(v: number) =>
                    t("dashboard.charts.hourLabel", { hour: `${String(v).padStart(2, "0")}:00` })
                  }
                />
                <Bar dataKey="count" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </GradientCardFrame>
  );
}
