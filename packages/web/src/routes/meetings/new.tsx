import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { ProtectedShell } from "../../components/protected-shell";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { MeetingApiError, useCreateMeetingMutation } from "../../lib/meetings-api";

export function NewMeeting() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  // Slice-7: pre-fill scheduled date from `?date=YYYY-MM-DD` query param
  // (used by the calendar empty-cell click). Default time = "09:00".
  const search = useSearch({ strict: false }) as { date?: string };
  const [title, setTitle] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [me, setMe] = useState("");
  const [scheduledDate, setScheduledDate] = useState<string>(search.date ?? "");
  const [scheduledTime, setScheduledTime] = useState<string>(search.date ? "09:00" : "");
  const [error, setError] = useState<string | null>(null);
  const mutation = useCreateMeetingMutation();
  const submitting = mutation.isPending;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      // Combine date + time into ISO 8601 (with the user's local TZ offset
      // → server stores as TIMESTAMPTZ). Both empty → null (unscheduled).
      let scheduledStartIso: string | null = null;
      if (scheduledDate) {
        const time = scheduledTime || "09:00";
        const local = new Date(`${scheduledDate}T${time}:00`);
        scheduledStartIso = Number.isNaN(local.getTime()) ? null : local.toISOString();
      }
      const meeting = await mutation.mutateAsync({
        title,
        counterparty_display_name: counterparty,
        me_display_name: me,
        scheduled_start_at: scheduledStartIso,
      });
      navigate({
        to: "/meetings/$id",
        params: { id: meeting.id },
        replace: true,
      });
    } catch (err) {
      if (err instanceof MeetingApiError && err.errorCode) {
        setError(localizedErrorMessage(err.errorCode, t));
      } else {
        setError(t("meetings.new.errorFallback"));
      }
    }
  }

  return (
    <ProtectedShell>
      <Card>
        <CardHeader>
          <CardTitle>{t("meetings.new.heading")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit} noValidate={false}>
            <div className="space-y-1">
              <Label htmlFor="meeting-title">{t("meetings.new.titleLabel")}</Label>
              <Input
                id="meeting-title"
                required
                value={title}
                placeholder={t("meetings.new.titlePlaceholder")}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="meeting-counterparty">{t("meetings.new.counterpartyLabel")}</Label>
              <Input
                id="meeting-counterparty"
                required
                value={counterparty}
                placeholder={t("meetings.new.counterpartyPlaceholder")}
                onChange={(e) => setCounterparty(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="meeting-me">{t("meetings.new.meLabel")}</Label>
              <Input
                id="meeting-me"
                required
                value={me}
                placeholder={t("meetings.new.mePlaceholder")}
                onChange={(e) => setMe(e.target.value)}
              />
            </div>

            {/* Slice-7: optional scheduled date + time. */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="meeting-date">{t("meetings.new.scheduledDateLabel")}</Label>
                <Input
                  id="meeting-date"
                  data-testid="meeting-date"
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => {
                    setScheduledDate(e.target.value);
                    if (e.target.value && !scheduledTime) setScheduledTime("09:00");
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="meeting-time">{t("meetings.new.scheduledTimeLabel")}</Label>
                <Input
                  id="meeting-time"
                  data-testid="meeting-time"
                  type="time"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                />
              </div>
            </div>

            {error && <Alert variant="destructive">{error}</Alert>}

            <div className="flex items-center gap-2">
              <Button type="submit" disabled={submitting}>
                {submitting ? t("meetings.new.submitting") : t("meetings.new.submit")}
              </Button>
              <Link to="/meetings" className={buttonVariants({ variant: "outline" })}>
                {t("meetings.new.cancel")}
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </ProtectedShell>
  );
}
