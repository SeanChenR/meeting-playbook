import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { ProtectedShell } from "../../components/protected-shell";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { meetingsListQueryOptions, MeetingApiError } from "../../lib/meetings-api";

export function MeetingsList() {
  const { t } = useTranslation();
  const query = useQuery(meetingsListQueryOptions());
  const meetings = query.data ?? null;
  const error = query.isError
    ? query.error instanceof MeetingApiError && query.error.errorCode
      ? localizedErrorMessage(query.error.errorCode, t)
      : t("errors.common.unknown")
    : null;

  return (
    <ProtectedShell>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("meetings.list.heading")}</h1>
        <div className="flex gap-2">
          <Link
            to="/meetings/calendar"
            className={buttonVariants({ variant: "outline" })}
            data-testid="meetings-toggle-calendar"
          >
            {t("meetings.list.toggleCalendar")}
          </Link>
          <Link to="/calendar/import" className={buttonVariants({ variant: "outline" })}>
            {t("meetings.list.fromCalendarButton")}
          </Link>
          <Link to="/meetings/new" className={buttonVariants()}>
            {t("meetings.list.newButton")}
          </Link>
        </div>
      </header>

      {error && (
        <Card>
          <CardContent className="text-destructive">{error}</CardContent>
        </Card>
      )}

      {meetings === null && !error && <div>{t("common.loading")}</div>}

      {meetings && meetings.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="text-4xl" aria-hidden>
              📋
            </div>
            <p className="text-base font-medium">{t("meetings.list.empty")}</p>
            <p className="max-w-sm text-sm text-(--color-muted-foreground)">
              {t("meetings.list.emptyHint")}
            </p>
          </CardContent>
        </Card>
      )}

      {meetings && meetings.length > 0 && (
        <ul className="space-y-3">
          {meetings.map((m) => (
            <li key={m.id}>
              <Link to={`/meetings/${m.id}`} className="block">
                <Card>
                  <CardHeader>
                    <CardTitle data-testid="meeting-list-item-title">{m.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-muted-foreground">
                    {m.counterparty_display_name} · {m.me_display_name}
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </ProtectedShell>
  );
}
