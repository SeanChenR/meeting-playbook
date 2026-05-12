/**
 * Meetings list — slice ui-overhaul-claude-design task 4.1.
 *
 * Visual contract aligned with design bundle `MeetingsList`:
 *   - Page header (title + meta "N 場 · 本週 M 場待進行")
 *   - Right controls: Tabs (卡片 / 日曆) + Calendar 匯入 + 新會議
 *   - 3-col responsive grid (`repeat(auto-fill, minmax(320px, 1fr))`)
 *   - Card: hover shadow + border升級, 3px left status color bar,
 *           status Badge dot+sm, title + counterparty/me row, bottom
 *           calendar icon + duration + optional `playbook` badge
 *   - No emoji anywhere — empty state copy stays neutral
 *
 * Tabs are visual-only here (the `日曆` triggers navigation to
 * /meetings/calendar via TanStack Router); stays consistent with the
 * existing test contract that reaches that route via the toggle link.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Calendar as CalendarIcon } from "lucide-react";
import { Plus } from "../../components/animate-ui/icons/plus";
import { useTranslation } from "react-i18next";
import { ProtectedShell } from "../../components/protected-shell";
import { Badge } from "../../components/ui/badge";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  type Meeting,
  type MeetingStatus,
  meetingsListQueryOptions,
  MeetingApiError,
} from "../../lib/meetings-api";

const STATUS_COLOR: Record<MeetingStatus, string> = {
  scheduled: "var(--color-primary)",
  in_progress: "var(--color-destructive)",
  completed: "var(--color-muted-foreground)",
};

const STATUS_BADGE: Record<MeetingStatus, "default" | "success" | "outline"> = {
  scheduled: "outline",
  in_progress: "success",
  completed: "default",
};

function _durationMinutes(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return Math.round(ms / 60000);
}

function _formatTime(value: string, locale: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MeetingsList() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const query = useQuery(meetingsListQueryOptions());
  const meetings = query.data ?? null;
  const error = query.isError
    ? query.error instanceof MeetingApiError && query.error.errorCode
      ? localizedErrorMessage(query.error.errorCode, t)
      : t("errors.common.unknown")
    : null;

  const total = meetings?.length ?? 0;
  const upcoming = meetings?.filter((m) => m.status !== "completed").length ?? 0;

  const handleViewChange = (next: string) => {
    if (next === "calendar") navigate({ to: "/meetings/calendar" });
  };

  return (
    <ProtectedShell>
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
            {t("meetings.list.heading")}
          </h1>
          {meetings && (
            <p className="text-sm text-(--color-muted-foreground)">
              {t("meetings.list.metaSummary", { total, upcoming })}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tabs value="grid" onValueChange={handleViewChange}>
            <TabsList className="h-9">
              <TabsTrigger value="grid" data-testid="meetings-tab-grid">
                {t("meetings.list.tabGrid")}
              </TabsTrigger>
              <TabsTrigger value="calendar" data-testid="meetings-toggle-calendar">
                {t("meetings.list.tabCalendar")}
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <Link
            to="/calendar/import"
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <CalendarIcon className="size-3.5" />
            {t("meetings.list.fromCalendarButton")}
          </Link>
          <Link to="/meetings/new" className={buttonVariants({ size: "sm" })}>
            <Plus animateOnHover className="size-3.5" />
            {t("meetings.list.newButtonShort")}
          </Link>
        </div>
      </header>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-(--color-destructive)">{error}</CardContent>
        </Card>
      )}

      {meetings === null && !error && (
        <p className="text-sm text-(--color-muted-foreground)">{t("common.loading")}</p>
      )}

      {meetings && meetings.length === 0 && (
        <Card data-testid="meetings-empty-state">
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <p className="text-base font-medium text-(--color-foreground)">
              {t("meetings.list.empty")}
            </p>
            <p className="max-w-sm text-sm text-(--color-muted-foreground)">
              {t("meetings.list.emptyHint")}
            </p>
          </CardContent>
        </Card>
      )}

      {meetings && meetings.length > 0 && (
        <ul
          data-testid="meetings-grid"
          className="grid gap-3.5"
          style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}
        >
          {meetings.map((m) => (
            <li key={m.id}>
              <MeetingGridCard meeting={m} locale={i18n.language} t={t} />
            </li>
          ))}
        </ul>
      )}
    </ProtectedShell>
  );
}

function MeetingGridCard({
  meeting,
  locale,
  t,
}: {
  meeting: Meeting;
  locale: string;
  t: (k: string) => string;
}) {
  const color = STATUS_COLOR[meeting.status];
  const badgeVariant = STATUS_BADGE[meeting.status];
  const duration = _durationMinutes(meeting.scheduled_start_at, meeting.scheduled_end_at);
  const timeText = meeting.scheduled_start_at
    ? _formatTime(meeting.scheduled_start_at, locale)
    : _formatTime(meeting.created_at, locale);

  return (
    <Link
      // Literal-path form: bypasses typed param resolution so the synthetic
      // test router renders an absolute href without the detail route in
      // its tree. Production runtime accepts both forms.
      {...({ to: `/meetings/${meeting.id}` } as { to: "/meetings/$id"; params: { id: string } })}
      data-testid="meeting-card"
      className="group relative block h-full overflow-hidden rounded-lg border border-(--color-border) bg-(--color-card) p-5 shadow-sm transition-[box-shadow,border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-(--color-primary)/40 hover:shadow-md"
    >
      <span
        aria-hidden
        className="absolute left-0 top-0 h-full w-[3px]"
        style={{ background: color }}
      />
      <div className="flex items-center justify-between gap-2">
        <Badge variant={badgeVariant} className="gap-1.5">
          <span aria-hidden className="size-1.5 rounded-full" style={{ background: color }} />
          {t(`meetings.list.status.${meeting.status}`)}
        </Badge>
      </div>
      <h2
        data-testid="meeting-list-item-title"
        className="mt-3 text-lg font-semibold leading-snug tracking-tight text-(--color-foreground)"
      >
        {meeting.title}
      </h2>
      <p className="mt-2 text-sm text-(--color-muted-foreground)">
        <span className="font-medium text-(--color-foreground)">
          {meeting.counterparty_display_name}
        </span>{" "}
        · {meeting.me_display_name}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--color-muted-foreground)">
        <span className="inline-flex items-center gap-1">
          <CalendarIcon className="size-3" aria-hidden />
          {timeText}
        </span>
        {duration !== null && (
          <span>
            · {duration} {t("meetings.list.minutesShort")}
          </span>
        )}
      </div>
    </Link>
  );
}
