import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ProtectedShell } from "../../components/protected-shell";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { createMeeting, MeetingApiError } from "../../lib/meetings-api";

export function NewMeeting() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [me, setMe] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const meeting = await createMeeting({
        title,
        counterparty_display_name: counterparty,
        me_display_name: me,
      });
      navigate(`/meetings/${meeting.id}`, { replace: true });
    } catch (err) {
      if (err instanceof MeetingApiError && err.errorCode) {
        setError(localizedErrorMessage(err.errorCode, t));
      } else {
        setError(t("meetings.new.errorFallback"));
      }
      setSubmitting(false);
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
