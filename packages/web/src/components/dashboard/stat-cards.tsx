/**
 * Dashboard StatCards — Sean revision 3.
 *
 * Four big-number cards: meeting count, average duration, total duration,
 * vs-previous-month percent change. Each card uses GradientCardFrame +
 * SpotlightCard so the dashboard polish matches the settings stack.
 */

import { ArrowDown, ArrowRight, ArrowUp, Clock3, Hourglass, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { GradientCardFrame } from "../magicui/gradient-card-frame";
import { NumberTicker } from "../magicui/number-ticker";
import type { DashboardStats } from "../../lib/stats-api";

interface StatCardsProps {
  stats: DashboardStats;
}

function _formatMinutes(seconds: number | null): { value: string; suffix: string } {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) {
    return { value: "—", suffix: "" };
  }
  const minutes = Math.round(seconds / 60);
  return { value: String(minutes), suffix: "min" };
}

function _formatHours(seconds: number): { value: string; suffix: string } {
  if (seconds <= 0) return { value: "0", suffix: "hr" };
  const hours = seconds / 3600;
  return { value: hours.toFixed(1), suffix: "hr" };
}

function _vsPrevPercent(current: number, prev: number): number | null {
  if (prev === 0) return current === 0 ? 0 : null;
  return Math.round(((current - prev) / prev) * 100);
}

export function StatCards({ stats }: StatCardsProps) {
  const { t } = useTranslation();
  const avg = _formatMinutes(stats.avg_duration_seconds);
  const total = _formatHours(stats.total_duration_seconds);
  const pct = _vsPrevPercent(stats.meeting_count, stats.prev_month_meeting_count);
  const delta = stats.meeting_count - stats.prev_month_meeting_count;

  return (
    <div className="grid auto-rows-fr grid-cols-2 gap-3 lg:grid-cols-4">
      <_StatCell
        testId="dashboard-stat-monthly_meetings"
        accent="var(--color-primary)"
        Icon={TrendingUp}
        label={t("dashboard.stat_cards.monthly_meetings")}
        value={String(stats.meeting_count)}
        deltaLabel={
          delta === 0
            ? undefined
            : delta > 0
              ? `+${delta} ${t("dashboard.stat_cards.deltaSuffix")}`
              : `${delta} ${t("dashboard.stat_cards.deltaSuffix")}`
        }
        deltaDirection={delta === 0 ? "flat" : delta > 0 ? "up" : "down"}
        animateNumeric={stats.meeting_count}
      />
      <_StatCell
        testId="dashboard-stat-average_duration"
        accent="var(--color-accent)"
        Icon={Clock3}
        label={t("dashboard.stat_cards.average_duration")}
        value={avg.value}
        suffix={avg.suffix}
      />
      <_StatCell
        testId="dashboard-stat-total_duration"
        accent="var(--color-primary)"
        Icon={Hourglass}
        label={t("dashboard.stat_cards.total_duration")}
        value={total.value}
        suffix={total.suffix}
      />
      <_StatCell
        testId="dashboard-stat-vs_previous"
        accent="var(--color-accent)"
        Icon={TrendingUp}
        label={t("dashboard.stat_cards.vs_previous")}
        value={pct === null ? "—" : `${pct >= 0 ? "+" : ""}${pct}%`}
        deltaDirection={pct === null ? "flat" : pct > 0 ? "up" : pct < 0 ? "down" : "flat"}
      />
    </div>
  );
}

interface StatCellProps {
  testId: string;
  accent: string;
  Icon: typeof TrendingUp;
  label: string;
  value: string;
  suffix?: string;
  deltaLabel?: string;
  deltaDirection?: "up" | "down" | "flat";
  animateNumeric?: number;
}

function _StatCell({
  testId,
  accent,
  Icon,
  label,
  value,
  suffix,
  deltaLabel,
  deltaDirection,
  animateNumeric,
}: StatCellProps) {
  const DeltaIcon =
    deltaDirection === "up" ? ArrowUp : deltaDirection === "down" ? ArrowDown : ArrowRight;
  const deltaColor =
    deltaDirection === "up"
      ? "text-(--color-accent)"
      : deltaDirection === "down"
        ? "text-(--color-destructive)"
        : "text-(--color-muted-foreground)";
  return (
    <GradientCardFrame
      data-testid={testId}
      accent={accent}
      accentAlt="var(--color-primary)"
      className="h-full"
      bodyClassName="h-full"
    >
      <div className="flex h-full flex-col items-center justify-center gap-2 rounded-[inherit] p-5 text-center">
        <div className="flex items-center justify-center gap-1.5 text-xs text-(--color-muted-foreground)">
          <Icon className="size-3.5" aria-hidden />
          <span>{label}</span>
        </div>
        <div className="flex items-baseline justify-center gap-1">
          {animateNumeric !== undefined && /^\d+$/.test(value) ? (
            <NumberTicker
              value={animateNumeric}
              className="text-3xl font-bold tracking-tight text-(--color-foreground)"
            />
          ) : (
            <span className="text-3xl font-bold tracking-tight text-(--color-foreground)">
              {value}
            </span>
          )}
          {suffix && <span className="text-sm text-(--color-muted-foreground)">{suffix}</span>}
        </div>
        {(deltaLabel || deltaDirection) && deltaDirection !== undefined && (
          <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${deltaColor}`}>
            <DeltaIcon className="size-3" />
            {deltaLabel}
          </span>
        )}
      </div>
    </GradientCardFrame>
  );
}
