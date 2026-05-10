/**
 * /meetings/calendar — Slice-07 month/week visualisation of the user's
 * meetings, plus a collapsible "Unscheduled" panel for meetings without
 * scheduled_start_at.
 *
 * Per spec meetings-calendar-view (NEW capability).
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Calendar, dateFnsLocalizer, type SlotInfo, Views } from "react-big-calendar";
import { format, getDay, parse, startOfWeek } from "date-fns";
import { enUS, zhTW } from "date-fns/locale";

import { ProtectedShell } from "../../components/protected-shell";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
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
  startOfWeek: (date: Date) => startOfWeek(date, { weekStartsOn: 1 /* Monday */ }),
  getDay,
  locales: { "en-US": enUS, "zh-TW": zhTW },
});

export function MeetingsCalendar() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [view, setView] = useState<"month" | "week">("month");
  const meetingsQuery = useQuery(meetingsListQueryOptions());

  const meetings: Meeting[] = useMemo(() => meetingsQuery.data ?? [], [meetingsQuery.data]);
  const events: CalendarEvent[] = useMemo(
    () => meetings.map(meetingToCalendarEvent).filter((e): e is CalendarEvent => e !== null),
    [meetings],
  );
  const unscheduled = useMemo(
    () => meetings.filter((m) => m.scheduled_start_at === null),
    [meetings],
  );
  const [unscheduledOpen, setUnscheduledOpen] = useState(false);

  const _formats = useMemo(
    () => ({
      monthHeaderFormat: i18n.language?.startsWith("zh") ? "yyyy年 M月" : "MMMM yyyy",
    }),
    [i18n.language],
  );

  return (
    <ProtectedShell>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("meetings.calendar.heading")}</h1>
        <Link to="/meetings" className={buttonVariants({ variant: "outline", size: "sm" })}>
          {t("meetings.calendar.toggleList")}
        </Link>
      </div>

      <Card>
        <CardContent className="pt-6" data-testid="meetings-calendar">
          <div style={{ height: 640 }}>
            <Calendar<CalendarEvent>
              localizer={_localizer}
              events={events}
              startAccessor="start"
              endAccessor="end"
              titleAccessor="title"
              views={[Views.MONTH, Views.WEEK]}
              view={view}
              onView={(v) => setView(v as "month" | "week")}
              defaultView={Views.MONTH}
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
              }}
              formats={_formats}
            />
          </div>
          {events.length === 0 && (
            <div
              data-testid="meetings-calendar-empty"
              className="mt-4 text-center text-sm text-(--color-muted-foreground)"
            >
              {t("meetings.calendar.empty")}
            </div>
          )}
        </CardContent>
      </Card>

      {unscheduled.length > 0 && (
        <Card data-testid="meetings-calendar-unscheduled">
          <CardHeader>
            <button
              type="button"
              onClick={() => setUnscheduledOpen((v) => !v)}
              aria-expanded={unscheduledOpen}
              className="flex w-full items-center justify-between text-left"
            >
              <CardTitle className="text-base">
                {t("meetings.calendar.unscheduledTitle")} ({unscheduled.length})
              </CardTitle>
              <span aria-hidden className="text-sm text-(--color-muted-foreground)">
                {unscheduledOpen ? "▾" : "▸"}
              </span>
            </button>
          </CardHeader>
          {unscheduledOpen && (
            <CardContent className="space-y-2">
              {unscheduled.map((m) => (
                <Link
                  key={m.id}
                  to="/meetings/$id"
                  params={{ id: m.id }}
                  data-testid={`unscheduled-row-${m.id}`}
                  className="block rounded-md border border-(--color-border) px-3 py-2 text-sm hover:bg-(--color-muted)"
                >
                  <div className="font-medium">{m.title}</div>
                  <div className="text-xs text-(--color-muted-foreground)">
                    {m.counterparty_display_name}
                  </div>
                </Link>
              ))}
            </CardContent>
          )}
        </Card>
      )}
    </ProtectedShell>
  );
}
