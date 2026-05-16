/**
 * DashboardBody — Sean revision 3.
 *
 * Top-level layout for `/dashboard`. State: the currently selected month
 * as a `YYYY-MM` string. Defaults to the current Asia/Taipei month.
 * Layout:
 *
 *   PeriodSwitcher                                                ←  →
 *   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
 *   │月會議數    │ │平均時長  │ │總時長     │ │ vs 上月  │   StatCards × 4
 *   └──────────┘ └──────────┘ └──────────┘ └──────────┘
 *   ┌──────────────────────────────────────────────────┐
 *   │  日趨勢 (area)                                    │   full width
 *   └──────────────────────────────────────────────────┘
 *   ┌────────────────────┬────────────────────────────┐
 *   │ Hour distribution  │  Calendar heatmap          │   half/half
 *   └────────────────────┴────────────────────────────┘
 *   ┌────────────────────┬────────────────────────────┐
 *   │ Top counterparties │  Tag distribution (S17)    │   half/half
 *   └────────────────────┴────────────────────────────┘
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { currentMonth, formatMonthLabel, useStatsQuery } from "../../lib/stats-api";
import { CalendarHeatmap } from "./calendar-heatmap";
import { DailyTrendChart } from "./daily-trend-chart";
import { HourDistributionChart } from "./hour-distribution-chart";
import { PeriodSwitcher } from "./period-switcher";
import { StatCards } from "./stat-cards";
import { TagDistributionChart } from "./tag-distribution-chart";
import { TopCounterpartiesChart } from "./top-counterparties-chart";

export function DashboardBody() {
  const { t, i18n } = useTranslation();
  const [month, setMonth] = useState<string>(() => currentMonth());
  const query = useStatsQuery(month);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
            {t("dashboard.title")}
          </h1>
          <p className="text-sm text-(--color-muted-foreground)">
            {formatMonthLabel(month, i18n.language)}
          </p>
        </div>
        <PeriodSwitcher value={month} onChange={setMonth} />
      </header>

      {query.isError && (
        <p data-testid="dashboard-error" className="text-sm text-(--color-destructive)">
          {t("dashboard.error")}
        </p>
      )}
      {query.isPending && (
        <p data-testid="dashboard-loading" className="text-sm text-(--color-muted-foreground)">
          {t("dashboard.loading")}
        </p>
      )}
      {query.data && (
        <>
          <StatCards stats={query.data} />
          <DailyTrendChart stats={query.data} />
          <div className="grid auto-rows-fr grid-cols-1 gap-4 lg:grid-cols-2">
            <HourDistributionChart stats={query.data} />
            <CalendarHeatmap stats={query.data} />
          </div>
          <div className="grid auto-rows-fr grid-cols-1 gap-4 lg:grid-cols-2">
            <TopCounterpartiesChart stats={query.data} />
            <TagDistributionChart stats={query.data} />
          </div>
        </>
      )}
    </div>
  );
}
