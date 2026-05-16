/**
 * MonthlyTrendChart — slice-18 task 5.2.
 *
 * Line chart of meeting counts per month from `DashboardStats.monthly_trend`.
 * Backend zero-fills missing months so the X axis stays uniformly spaced.
 */

import { useTranslation } from "react-i18next";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardStats } from "../../lib/stats-api";
import { Card, CardContent } from "../ui/card";

interface Props {
  stats: DashboardStats;
}

export function MonthlyTrendChart({ stats }: Props) {
  const { t } = useTranslation();
  const data = stats.monthly_trend;

  return (
    <Card data-testid="dashboard-chart-monthly-trend">
      <CardContent className="space-y-3 p-4">
        <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
          {t("dashboard.charts.monthly_trend")}
        </h3>
        {data.length === 0 ? (
          <p className="text-xs text-(--color-muted-foreground)">{t("dashboard.empty")}</p>
        ) : (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="month" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "var(--color-primary)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
