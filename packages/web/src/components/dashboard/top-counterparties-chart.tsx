/**
 * TopCounterpartiesChart — Sean revision 3.
 *
 * Horizontal bar chart of the top counterparties for the selected month.
 * Wrapped in GradientCardFrame so the visual matches the rest of the
 * dashboard stack; `h-full` lets the grid row stretch both siblings to
 * the same height.
 */

import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardStats } from "../../lib/stats-api";
import { GradientCardFrame } from "../magicui/gradient-card-frame";

interface Props {
  stats: DashboardStats;
}

export function TopCounterpartiesChart({ stats }: Props) {
  const { t } = useTranslation();
  const data = stats.top_counterparties;

  return (
    <GradientCardFrame
      data-testid="dashboard-chart-top-counterparties"
      disableHover
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
      className="h-full"
      bodyClassName="h-full"
    >
      <div className="flex h-full flex-col rounded-[inherit] p-5">
        <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
          {t("dashboard.charts.top_counterparties")}
        </h3>
        {data.length === 0 ? (
          <p className="flex-1 py-10 text-center text-xs text-(--color-muted-foreground)">
            {t("dashboard.empty")}
          </p>
        ) : (
          <div className="mt-4 min-h-[260px] flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 16, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="display_name"
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  width={80}
                />
                <Tooltip
                  cursor={{ fill: "var(--color-muted)" }}
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="count" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </GradientCardFrame>
  );
}
