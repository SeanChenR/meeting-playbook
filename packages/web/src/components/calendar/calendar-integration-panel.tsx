/**
 * CalendarIntegrationPanel — slice-19 task 4.1.
 *
 * Extracted from `routes/calendar/upcoming.tsx` so the same connection +
 * upcoming-events surface can render inside `/settings/integrations`
 * without the `BackLink` / `ProtectedShell` wrapper. The legacy route
 * keeps that wrapper; this component is shell-agnostic.
 */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw } from "../animate-ui/icons/refresh-cw";
import { Sparkles } from "../animate-ui/icons/sparkles";
import { Alert } from "../ui/alert";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { authClient } from "../../lib/auth-client";
import {
  CalendarApiError,
  upcomingEventsQueryOptions,
  useImportFromCalendarMutation,
  type UpcomingEvent,
} from "../../lib/calendar-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";

const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";

function _formatDate(iso: string, locale: string): { month: string; day: string; full: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { month: "", day: "?", full: iso };
  const isZh = locale?.startsWith("zh");
  const month = isZh ? `${d.getMonth() + 1}月` : d.toLocaleString("en", { month: "short" });
  const day = String(d.getDate());
  const full = d.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return { month, day, full };
}

export interface CalendarIntegrationPanelProps {
  /** When true, skip the heading/subhead row. Header context lives in the
   *  parent (e.g. settings hero card already names the integration). The
   *  refresh button still renders, just promoted to the panel top-right. */
  hideHeader?: boolean;
}

export function CalendarIntegrationPanel({
  hideHeader = false,
}: CalendarIntegrationPanelProps = {}) {
  const { t, i18n } = useTranslation();
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
      <Card data-testid="calendar-integration-disconnected">
        <CardHeader>
          <CardTitle>{t("calendar.heading")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-(--color-muted-foreground)">{t("calendar.connect.description")}</p>
          <Button
            data-testid="calendar-connect-cta"
            onClick={() => {
              authClient.linkSocial({
                provider: "google",
                scopes: [CALENDAR_SCOPE],
                callbackURL: "/settings/integrations",
              });
            }}
          >
            {t("calendar.connect.cta")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div data-testid="calendar-integration-panel" className="space-y-4">
      {hideHeader ? (
        <div className="flex justify-end">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            data-testid="calendar-refresh"
          >
            <RefreshCw
              animate={query.isFetching ? "rotate" : undefined}
              animateOnHover
              className="size-3.5"
            />
            {t("calendar.refresh")}
          </Button>
        </div>
      ) : (
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-(--color-foreground)">
              {t("calendar.heading")}
            </h1>
            <p className="text-sm text-(--color-muted-foreground)">{t("calendar.subhead")}</p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            data-testid="calendar-refresh"
          >
            <RefreshCw
              animate={query.isFetching ? "rotate" : undefined}
              animateOnHover
              className="size-3.5"
            />
            {t("calendar.refresh")}
          </Button>
        </header>
      )}

      {error && <Alert variant="destructive">{error}</Alert>}

      {query.isLoading && (
        <p className="text-sm text-(--color-muted-foreground)">{t("calendar.loading")}</p>
      )}

      {query.data && query.data.length === 0 && (
        <Card data-testid="calendar-integration-empty">
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <p className="text-base font-medium text-(--color-foreground)">{t("calendar.empty")}</p>
            <p className="max-w-sm text-sm text-(--color-muted-foreground)">
              {t("calendar.emptyHint")}
            </p>
          </CardContent>
        </Card>
      )}

      {query.data && query.data.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <ul>
              {query.data.map((evt: UpcomingEvent, i: number) => (
                <_EventRow
                  key={evt.id}
                  evt={evt}
                  locale={i18n.language}
                  importing={importingId === evt.id}
                  importingAny={importingId !== null}
                  onImport={() => handleImport(evt.id)}
                  isFirst={i === 0}
                  t={t}
                />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function _EventRow({
  evt,
  locale,
  importing,
  importingAny,
  onImport,
  isFirst,
  t,
}: {
  evt: UpcomingEvent;
  locale: string;
  importing: boolean;
  importingAny: boolean;
  onImport: () => void;
  isFirst: boolean;
  t: (k: string, v?: Record<string, unknown>) => string;
}) {
  const { month, day, full } = _formatDate(evt.start, locale);
  return (
    <li
      data-testid={`calendar-event-${evt.id}`}
      className={`flex items-center gap-4 px-5 py-4 ${
        isFirst ? "" : "border-t border-(--color-border)"
      }`}
    >
      <div className="flex size-[42px] shrink-0 flex-col items-center justify-center rounded-md bg-(--color-muted)/50">
        <span className="text-xs font-semibold text-(--color-primary)">{day}</span>
        <span className="text-[9px] text-(--color-muted-foreground)">{month}</span>
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="truncate text-sm font-medium text-(--color-foreground)">{evt.title}</p>
        <p data-testid="calendar-row-attendees" className="text-xs text-(--color-muted-foreground)">
          {full} · {t("calendar.row.attendees", { count: evt.attendees.length })}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        onClick={onImport}
        disabled={importingAny}
        data-testid={`calendar-import-${evt.id}`}
      >
        <Sparkles animateOnHover className="size-3.5" />
        {importing ? t("calendar.row.importing") : t("calendar.row.import")}
      </Button>
    </li>
  );
}
