import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ProtectedShell } from "../../components/protected-shell";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { authClient } from "../../lib/auth-client";
import {
  CalendarApiError,
  upcomingEventsQueryOptions,
  useImportFromCalendarMutation,
  type UpcomingEvent,
} from "../../lib/calendar-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";

const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";

export function UpcomingEvents() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useQuery(upcomingEventsQueryOptions(24));
  const importMutation = useImportFromCalendarMutation();
  const [importError, setImportError] = useState<string | null>(null);
  const [importingId, setImportingId] = useState<string | null>(null);

  async function handleImport(eventId: string) {
    setImportError(null);
    setImportingId(eventId);
    try {
      const { meeting_id } = await importMutation.mutateAsync(eventId);
      navigate({ to: "/meetings/$id", params: { id: meeting_id }, replace: true });
    } catch (err) {
      if (err instanceof CalendarApiError && err.errorCode) {
        setImportError(localizedErrorMessage(err.errorCode, t));
      } else {
        setImportError(t("errors.common.unknown"));
      }
      setImportingId(null);
    }
  }

  const isNotConnected =
    query.isError &&
    query.error instanceof CalendarApiError &&
    query.error.errorCode === "calendar.not_connected";
  const fetchError =
    query.isError && !isNotConnected
      ? query.error instanceof CalendarApiError && query.error.errorCode
        ? localizedErrorMessage(query.error.errorCode, t)
        : t("errors.common.unknown")
      : null;
  const error = importError ?? fetchError;

  if (isNotConnected) {
    return (
      <ProtectedShell>
        <Card>
          <CardHeader>
            <CardTitle>{t("calendar.heading")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="text-(--color-muted-foreground)">{t("calendar.connect.description")}</p>
            <Button
              data-testid="calendar-connect-cta"
              onClick={() => {
                // Better Auth client triggers a top-level navigation so the
                // OAuth state cookie is set and Google's consent screen loads
                // in the browser (not via fetch, which can't navigate).
                authClient.linkSocial({
                  provider: "google",
                  scopes: [CALENDAR_SCOPE],
                  callbackURL: "/calendar/import",
                });
              }}
            >
              {t("calendar.connect.cta")}
            </Button>
          </CardContent>
        </Card>
      </ProtectedShell>
    );
  }

  return (
    <ProtectedShell>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("calendar.heading")}</h1>
      </header>

      {error && <Alert variant="destructive">{error}</Alert>}

      {query.isLoading && <div>{t("calendar.loading")}</div>}

      {query.data && query.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="text-4xl" aria-hidden>
              📅
            </div>
            <p className="text-base font-medium">{t("calendar.empty")}</p>
            <p className="max-w-sm text-sm text-(--color-muted-foreground)">
              {t("calendar.emptyHint")}
            </p>
          </CardContent>
        </Card>
      )}

      {query.data && query.data.length > 0 && (
        <ul className="space-y-3">
          {query.data.map((evt: UpcomingEvent) => (
            <li key={evt.id}>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between gap-3">
                  <div>
                    <CardTitle>{evt.title}</CardTitle>
                    <p className="mt-1 text-xs text-(--color-muted-foreground)">
                      {new Date(evt.start).toLocaleString()}
                    </p>
                    <p
                      className="mt-1 text-xs text-(--color-muted-foreground)"
                      data-testid="calendar-row-attendees"
                    >
                      {t("calendar.row.attendees", { count: evt.attendees.length })}
                    </p>
                  </div>
                  <Button onClick={() => handleImport(evt.id)} disabled={importingId !== null}>
                    {importingId === evt.id
                      ? t("calendar.row.importing")
                      : t("calendar.row.import")}
                  </Button>
                </CardHeader>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </ProtectedShell>
  );
}
