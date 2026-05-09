import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CaptureIndicator, type CaptureState } from "../../components/capture-indicator";
import { PlaybookPane } from "../../components/playbook-pane";
import { ProtectedShell } from "../../components/protected-shell";
import { TranscriptPane } from "../../components/transcript-pane";
import { useMeetingSession } from "../../hooks/use-meeting-session";
import { rowToMessage, transcriptChunksQueryOptions } from "../../lib/transcripts-api";
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
  const session = useMeetingSession(meetingId);

  const captureState: CaptureState =
    session.state.phase === "in_progress"
      ? session.state.silenceSince !== null
        ? "silence_warning"
        : "active"
      : session.state.phase === "ending"
        ? "ending"
        : "idle";
  const liveChunks =
    session.state.phase === "in_progress" ||
    session.state.phase === "ending" ||
    session.state.phase === "ended" ||
    session.state.phase === "error"
      ? session.state.chunks
      : [];
  // Fetch historical transcript chunks for completed / in_progress meetings
  // (skip while still scheduled — nothing to show). Live chunks from the
  // current WS session take precedence; outside in_progress we display the
  // historical query result so a refreshed page on a completed meeting
  // still shows the transcript.
  const historyQuery = useQuery(
    transcriptChunksQueryOptions(
      meetingId,
      meeting !== null && meeting.status !== "scheduled" && session.state.phase !== "in_progress",
    ),
  );
  const sessionChunks =
    liveChunks.length > 0 ? liveChunks : (historyQuery.data ?? []).map(rowToMessage);
  const sessionError =
    session.state.phase === "error" ? localizedErrorMessage(session.state.errorCode, t) : null;
  // Start is allowed only when (a) the meeting is still scheduled and
  // (b) we haven't already opened a session in this view. Once status
  // advances to in_progress / completed, Start stays disabled — meeting
  // session is one-shot per spec (transcripts + recording overwrite would
  // otherwise be ambiguous).
  const startDisabled =
    !meeting ||
    meeting.status !== "scheduled" ||
    session.state.phase === "connecting" ||
    session.state.phase === "in_progress" ||
    session.state.phase === "ending";
  // End is enabled only while a session is actively in progress; once
  // "ending" we lock it (server is draining). Show a "結束中…" label too.
  const endDisabled = session.state.phase !== "in_progress";
  const endLabel =
    session.state.phase === "ending" ? t("meetings.session.ending") : t("meetings.session.end");
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
            <div className="flex flex-wrap items-center gap-3 pt-4">
              <Button onClick={session.start} disabled={startDisabled}>
                {t("meetings.session.start")}
              </Button>
              <Button variant="outline" onClick={session.end} disabled={endDisabled}>
                {endLabel}
              </Button>
              <CaptureIndicator state={captureState} />
              <Button
                variant="destructive"
                onClick={() => setConfirmOpen(true)}
                className="ml-auto"
              >
                {t("meetings.detail.deleteButton")}
              </Button>
            </div>
            {sessionError && <Alert variant="destructive">{sessionError}</Alert>}
          </CardContent>
        </Card>
      )}

      {meeting && <PlaybookPane meetingId={meetingId} />}
      {meeting && <TranscriptPane chunks={sessionChunks} meDisplayName={meeting.me_display_name} />}

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
