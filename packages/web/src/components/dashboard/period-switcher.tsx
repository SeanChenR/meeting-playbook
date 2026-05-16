/**
 * PeriodSwitcher — Sean revision 3 (month-arrow picker).
 *
 * `← month label →` triple. The arrows step the active month one
 * forward / backward. Disabled when at the boundary (we cap the
 * forward arrow at the current Asia/Taipei month so dashboards can't
 * be "looking into the future").
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { currentMonth, formatMonthLabel, shiftMonth } from "../../lib/stats-api";

interface PeriodSwitcherProps {
  value: string; // YYYY-MM
  onChange: (next: string) => void;
}

export function PeriodSwitcher({ value, onChange }: PeriodSwitcherProps) {
  const { i18n, t } = useTranslation();
  const now = currentMonth();
  const isCurrent = value >= now;
  const label = formatMonthLabel(value, i18n.language);

  return (
    <div
      data-testid="dashboard-period-switcher"
      className="inline-flex items-center gap-1 rounded-md border border-(--color-border) bg-(--color-card) p-1"
    >
      <button
        type="button"
        data-testid="dashboard-period-prev"
        onClick={() => onChange(shiftMonth(value, -1))}
        aria-label={t("dashboard.period.previousMonth")}
        className="inline-flex size-7 items-center justify-center rounded-sm text-(--color-muted-foreground) hover:bg-(--color-muted) hover:text-(--color-foreground)"
      >
        <ChevronLeft className="size-4" />
      </button>
      <span
        data-testid="dashboard-period-label"
        className="px-3 text-sm font-medium text-(--color-foreground)"
      >
        {label}
      </span>
      <button
        type="button"
        data-testid="dashboard-period-next"
        onClick={() => onChange(shiftMonth(value, 1))}
        disabled={isCurrent}
        aria-label={t("dashboard.period.nextMonth")}
        className="inline-flex size-7 items-center justify-center rounded-sm text-(--color-muted-foreground) hover:bg-(--color-muted) hover:text-(--color-foreground) disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  );
}
