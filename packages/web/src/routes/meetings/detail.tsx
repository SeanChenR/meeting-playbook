import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ProtectedShell } from "../../components/protected-shell";
import { AlertDialog } from "../../components/ui/alert-dialog";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { deleteMeeting, getMeeting, type Meeting, MeetingApiError } from "../../lib/meetings-api";

export function MeetingDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id = "" } = useParams<{ id: string }>();

  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!id) return;
    (async () => {
      try {
        const m = await getMeeting(id);
        if (!cancelled) setMeeting(m);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof MeetingApiError && e.errorCode) {
          setError(localizedErrorMessage(e.errorCode, t));
        } else {
          setError(t("meetings.detail.errorFallback"));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, t]);

  async function handleConfirmDelete() {
    if (!id) return;
    try {
      await deleteMeeting(id);
      navigate("/meetings", { replace: true });
    } catch (e) {
      if (e instanceof MeetingApiError && e.errorCode) {
        setError(localizedErrorMessage(e.errorCode, t));
      } else {
        setError(t("meetings.detail.errorFallback"));
      }
    }
  }

  return (
    <ProtectedShell>
      <Link to="/meetings" className={buttonVariants({ variant: "ghost", size: "sm" })}>
        {t("meetings.detail.back")}
      </Link>

      {error && <Alert variant="destructive">{error}</Alert>}

      {meeting === null && !error && <div>{t("common.loading")}</div>}

      {meeting && (
        <Card>
          <CardHeader>
            <CardTitle>{meeting.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="font-medium">{t("meetings.detail.counterpartyLabel")}：</span>
              <span>{meeting.counterparty_display_name}</span>
            </div>
            <div>
              <span className="font-medium">{t("meetings.detail.meLabel")}：</span>
              <span>{meeting.me_display_name}</span>
            </div>
            <div>
              <span className="font-medium">{t("meetings.detail.statusLabel")}：</span>
              <span>{t(`meetings.status.${meeting.status}`)}</span>
            </div>
            <div>
              <span className="font-medium">{t("meetings.detail.asrProviderLabel")}：</span>
              <span>{meeting.asr_provider}</span>
            </div>
            <div>
              <span className="font-medium">{t("meetings.detail.createdAtLabel")}：</span>
              <span>{new Date(meeting.created_at).toLocaleString()}</span>
            </div>
            <div className="pt-4">
              <Button variant="destructive" onClick={() => setConfirmOpen(true)}>
                {t("meetings.detail.deleteButton")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <AlertDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("meetings.detail.deleteDialogTitle")}
        description={t("meetings.detail.deleteDialogDescription")}
        confirmLabel={t("meetings.detail.deleteConfirm")}
        cancelLabel={t("meetings.detail.deleteCancel")}
        onConfirm={handleConfirmDelete}
        destructive
      />
    </ProtectedShell>
  );
}
