/**
 * /meetings/calendar — slice ui-overhaul-claude-design task 4.3.
 *
 * Visual contract aligned with design bundle `CalendarScreen`:
 *   - Page header (title + meta `年 月 · 第 N 週`)
 *   - Right controls: shadcn Tabs (月/週) + prev / today / next +
 *     `新會議` primary
 *   - Main grid `1fr 280px`:
 *       left  → react-big-calendar (month / week views — chrome
 *               hidden because controls live in the header) inside a Card
 *       right → `未排程` sidebar Card listing meetings with no schedule;
 *               each row offers `排定` (→ /meetings/$id) + `隱藏` (local
 *               dismiss; not persisted)
 *
 * Per Decision 7, demo data is reference-only — the grid renders the
 * real meetings list. The week-number meta uses ISO 8601 week numbers.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Calendar, dateFnsLocalizer, Navigate, type SlotInfo, Views } from "react-big-calendar";
import { format, getDay, getISOWeek, parse, startOfWeek } from "date-fns";
import { enUS, zhTW } from "date-fns/locale";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Plus } from "../../components/animate-ui/icons/plus";

import { BackLink } from "../../components/back-link";
import { ProtectedShell } from "../../components/protected-shell";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { meetingsListQueryOptions, type Meeting } from "../../lib/meetings-api";
import {
  meetingToCalendarEvent,
  statusToEventClassName,
  type CalendarEvent,
} from "../../lib/meetings-calendar-utils";
import "react-big-calendar/lib/css/react-big-calendar.css";

const _localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { weekStartsOn: 1 }),
  getDay,
  locales: { "en-US": enUS, "zh-TW": zhTW },
});

type View = "month" | "week";

export function MeetingsCalendar() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [view, setView] = useState<View>("week");
  const [cursor, setCursor] = useState<Date>(new Date());
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const meetingsQuery = useQuery(meetingsListQueryOptions());
  const meetings: Meeting[] = useMemo(() => meetingsQuery.data ?? [], [meetingsQuery.data]);
  const events: CalendarEvent[] = useMemo(
    () => meetings.map(meetingToCalendarEvent).filter((e): e is CalendarEvent => e !== null),
    [meetings],
  );
  const unscheduled = useMemo(
    () => meetings.filter((m) => m.scheduled_start_at === null && !hidden.has(m.id)),
    [meetings, hidden],
  );

  const isZh = i18n.language?.startsWith("zh");
  const yearMonth = isZh
    ? format(cursor, "yyyy年 M月")
    : format(cursor, "MMMM yyyy", { locale: enUS });
  const weekNumber = getISOWeek(cursor);

  const _formats = useMemo(
    () => ({
      monthHeaderFormat: isZh ? "yyyy年 M月" : "MMMM yyyy",
    }),
    [isZh],
  );

  const handleNavigate = (action: "PREV" | "NEXT" | "TODAY") => {
    if (action === "TODAY") {
      setCursor(new Date());
      return;
    }
    const next = new Date(cursor);
    const step = view === "month" ? 1 : 7;
    if (view === "month") {
      next.setMonth(cursor.getMonth() + (action === "NEXT" ? 1 : -1));
    } else {
      next.setDate(cursor.getDate() + (action === "NEXT" ? step : -step));
    }
    setCursor(next);
  };

  return (
    <ProtectedShell fullBleed>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-6 pt-5">
        <BackLink to="/meetings" />
        <header
          data-testid="calendar-header"
          className="flex flex-wrap items-center justify-between gap-4"
        >
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
              {t("meetings.calendar.heading")}
            </h1>
            <p className="text-sm text-(--color-muted-foreground)">
              {t("meetings.calendar.meta", { yearMonth, week: weekNumber })}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs value={view} onValueChange={(v) => setView(v as View)}>
              <TabsList className="h-9">
                <TabsTrigger value="month" data-testid="calendar-tab-month">
                  {t("meetings.calendar.viewMonth")}
                </TabsTrigger>
                <TabsTrigger value="week" data-testid="calendar-tab-week">
                  {t("meetings.calendar.viewWeek")}
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={t("meetings.calendar.prev")}
              onClick={() => handleNavigate("PREV")}
              data-testid="calendar-prev"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleNavigate("TODAY")}
              data-testid="calendar-today"
            >
              {t("meetings.calendar.today")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={t("meetings.calendar.next")}
              onClick={() => handleNavigate("NEXT")}
              data-testid="calendar-next"
            >
              <ChevronRight className="size-4" />
            </Button>
            <Link to="/meetings/new" className={buttonVariants({ size: "sm" })}>
              <Plus animateOnHover className="size-3.5" />
              {t("meetings.calendar.newMeeting")}
            </Link>
          </div>
        </header>

        <div className="grid gap-4" style={{ gridTemplateColumns: "minmax(0, 1fr) 280px" }}>
          <Card>
            <CardContent className="p-0" data-testid="meetings-calendar">
              <div style={{ height: 640 }}>
                <Calendar<CalendarEvent>
                  localizer={_localizer}
                  events={events}
                  startAccessor="start"
                  endAccessor="end"
                  titleAccessor="title"
                  views={[Views.MONTH, Views.WEEK]}
                  view={view}
                  date={cursor}
                  onView={(v) => setView(v as View)}
                  onNavigate={(d) => setCursor(d as Date)}
                  toolbar={false}
                  selectable
                  onSelectEvent={(ev) => navigate({ to: "/meetings/$id", params: { id: ev.id } })}
                  onSelectSlot={(slot: SlotInfo) => {
                    const date = format(slot.start, "yyyy-MM-dd");
                    navigate({ to: "/meetings/new", search: { date } });
                  }}
                  eventPropGetter={(ev) => ({
                    className: statusToEventClassName(ev.resource.status),
                  })}
                  messages={{
                    month: t("meetings.calendar.viewMonth"),
                    week: t("meetings.calendar.viewWeek"),
                    today: t("meetings.calendar.today"),
                    next: t("meetings.calendar.next"),
                    previous: t("meetings.calendar.prev"),
                  }}
                  formats={_formats}
                />
              </div>
              {events.length === 0 && (
                <div
                  data-testid="meetings-calendar-empty"
                  className="border-t border-(--color-border) py-4 text-center text-sm text-(--color-muted-foreground)"
                >
                  {t("meetings.calendar.empty")}
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="meetings-calendar-unscheduled">
            <CardContent className="space-y-3 p-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-(--color-foreground)">
                  {t("meetings.calendar.unscheduledTitle")}
                </p>
                <p className="text-xs text-(--color-muted-foreground)">
                  {t("meetings.calendar.unscheduledHint")}
                </p>
              </div>
              {unscheduled.length === 0 && (
                <p className="rounded-md bg-(--color-muted)/40 px-3 py-4 text-center text-xs text-(--color-muted-foreground)">
                  {t("meetings.calendar.unscheduledEmpty")}
                </p>
              )}
              {unscheduled.map((m) => (
                <div
                  key={m.id}
                  data-testid={`unscheduled-row-${m.id}`}
                  className="space-y-2 rounded-md border border-(--color-border) bg-(--color-card) p-3"
                >
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-(--color-foreground)">{m.title}</p>
                    <p className="text-xs text-(--color-muted-foreground)">
                      {m.counterparty_display_name}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      {...({ to: `/meetings/${m.id}` } as {
                        to: "/meetings/$id";
                        params: { id: string };
                      })}
                      className={buttonVariants({ size: "sm" })}
                    >
                      {t("meetings.calendar.unscheduledSchedule")}
                    </Link>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setHidden((s) => {
                          const next = new Set(s);
                          next.add(m.id);
                          return next;
                        })
                      }
                    >
                      {t("meetings.calendar.unscheduledHide")}
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedShell>
  );
}

// Suppress unused-import warning for `Navigate` from react-big-calendar
// (kept as re-export anchor in case future code re-introduces the toolbar).
export const _CalendarNavigate = Navigate;
