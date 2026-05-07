import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ProtectedShell } from "../../components/protected-shell";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { listMeetings, type Meeting, MeetingApiError } from "../../lib/meetings-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";

export function MeetingsList() {
  const { t } = useTranslation();
  const [meetings, setMeetings] = useState<Meeting[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await listMeetings();
        if (!cancelled) setMeetings(rows);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof MeetingApiError && e.errorCode) {
          setError(localizedErrorMessage(e.errorCode, t));
        } else {
          setError(t("errors.common.unknown"));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <ProtectedShell>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("meetings.list.heading")}</h1>
        <Link to="/meetings/new" className={buttonVariants()}>
          {t("meetings.list.newButton")}
        </Link>
      </header>

      {error && (
        <Card>
          <CardContent className="text-destructive">{error}</CardContent>
        </Card>
      )}

      {meetings === null && !error && <div>{t("common.loading")}</div>}

      {meetings && meetings.length === 0 && (
        <Card>
          <CardContent className="text-center text-muted-foreground">
            {t("meetings.list.empty")}
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
