import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PlaybookPane } from "../../components/playbook-pane";
import { ProtectedShell } from "../../components/protected-shell";
import { AlertDialog } from "../../components/ui/alert-dialog";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  meetingQueryOptions,
  MeetingApiError,
  useDeleteMeetingMutation,
} from "../../lib/meetings-api";

export function MeetingDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams({ strict: false }) as { id?: string };
  const meetingId = id ?? "";

  const query = useQuery({ ...meetingQueryOptions(meetingId), enabled: !!meetingId });
  const deleteMutation = useDeleteMeetingMutation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const meeting = query.data ?? null;
  const fetchError =
    query.isError && query.error instanceof MeetingApiError && query.error.errorCode
      ? localizedErrorMessage(query.error.errorCode, t)
      : query.isError
        ? t("meetings.detail.errorFallback")
        : null;
  const error = deleteError ?? fetchError;

  async function handleConfirmDelete() {
    if (!meetingId) return;
    setDeleteError(null);
    try {
      await deleteMutation.mutateAsync(meetingId);
      navigate({ to: "/meetings", replace: true });
    } catch (e) {
      if (e instanceof MeetingApiError && e.errorCode) {
        setDeleteError(localizedErrorMessage(e.errorCode, t));
      } else {
        setDeleteError(t("meetings.detail.errorFallback"));
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

      {meeting && <PlaybookPane meetingId={meetingId} />}

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
