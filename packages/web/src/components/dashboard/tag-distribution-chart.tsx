/**
 * TagDistributionChart — Sean revision 3.
 *
 * Donut chart of tag counts. Empty until slice-17 ships and meetings start
 * carrying tag rows. `h-full` stretches the card to match its grid sibling.
 */

import { useTranslation } from "react-i18next";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { DashboardStats } from "../../lib/stats-api";
import { GradientCardFrame } from "../magicui/gradient-card-frame";

interface Props {
  stats: DashboardStats;
}

const _COLOR_VARS = [
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-primary)",
  "var(--color-muted-foreground)",
  "var(--color-accent)",
];

export function TagDistributionChart({ stats }: Props) {
  const { t } = useTranslation();
  const data = stats.tag_distribution;

  return (
    <GradientCardFrame
      data-testid="dashboard-chart-tag-distribution"
      disableHover
      accent="var(--color-accent)"
      accentAlt="var(--color-primary)"
      className="h-full"
      bodyClassName="h-full"
    >
      <div className="flex h-full flex-col rounded-[inherit] p-5">
        <h3 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
          {t("dashboard.charts.tag_distribution")}
        </h3>
        {data.length === 0 ? (
          <p className="flex-1 py-10 text-center text-xs text-(--color-muted-foreground)">
            {t("dashboard.empty")}
          </p>
        ) : (
          <div className="mt-4 min-h-[260px] flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  dataKey="count"
                  nameKey="tag"
                  innerRadius={36}
                  outerRadius={70}
                  paddingAngle={2}
                >
                  {data.map((entry, idx) => (
                    <Cell key={entry.tag} fill={_COLOR_VARS[idx % _COLOR_VARS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </GradientCardFrame>
  );
}
