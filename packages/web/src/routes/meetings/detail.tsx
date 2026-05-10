import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CaptureIndicator } from "../../components/capture-indicator";
import { HeadphonesHint } from "../../components/headphones-hint";
import { LayoutSwitcher } from "../../components/layout-switcher";
import { PlaybookPane } from "../../components/playbook-pane";
import { ProtectedShell } from "../../components/protected-shell";
import { TranscriptPane } from "../../components/transcript-pane";
import { useDetailLayout } from "../../hooks/use-detail-layout";
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

function AdvisorPlaceholder() {
  const { t } = useTranslation();
  return (
    <Card data-testid="advisor-placeholder">
      <CardHeader>
        <CardTitle>Advisor</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-(--color-muted-foreground)">
        {t("meetings.detail.advisorPlaceholder")}
      </CardContent>
    </Card>
  );
}

export function MeetingDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams({ strict: false }) as { id?: string };
  const meetingId = id ?? "";

  const query = useQuery({ ...meetingQueryOptions(meetingId), enabled: !!meetingId });
  const deleteMutation = useDeleteMeetingMutation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [layout, setLayout] = useDetailLayout();

  const meeting = query.data ?? null;
  const session = useMeetingSession(meetingId);

  // Slice-7: derive per-stream pill state for the indicator. Outside an
  // active session (idle / connecting / ended / error) the indicator is
  // hidden by passing `streamStatus={null}`.
  const indicatorStreamStatus =
    session.state.phase === "in_progress" || session.state.phase === "ending"
      ? session.state.streamStatus
      : null;
  const liveChunks =
    session.state.phase === "in_progress" ||
    session.state.phase === "ending" ||
    session.state.phase === "ended" ||
    session.state.phase === "error"
      ? session.state.chunks
      : [];
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
  const startDisabled =
    !meeting ||
    meeting.status !== "scheduled" ||
    session.state.phase === "connecting" ||
    session.state.phase === "in_progress" ||
    session.state.phase === "ending";
  // Slice-7 round 3: End button is hidden entirely once the user clicks End.
  // Server is draining queued audio; the "ending" state lives on the
  // CaptureIndicator pulse + the muted "結束中…" indicator. No second click
  // possible → no need to keep a disabled-but-visible button competing for
  // attention.
  const showEndButton = session.state.phase === "in_progress";
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

  // Three workspace panes — rendered identically in both layouts; the
  // wrapper element decides the geometry (3-col grid vs vertical stack).
  const playbookPane = meeting && <PlaybookPane meetingId={meetingId} />;
  const transcriptPane = meeting && (
    <TranscriptPane
      chunks={sessionChunks}
      meDisplayName={meeting.me_display_name}
      counterpartyDisplayName={meeting.counterparty_display_name}
    />
  );
  const advisorPane = meeting && <AdvisorPlaceholder />;

  return (
    <ProtectedShell fullBleed>
      <div className="flex items-center justify-between">
        <Link to="/meetings" className={buttonVariants({ variant: "ghost", size: "sm" })}>
          {t("meetings.detail.back")}
        </Link>
        <LayoutSwitcher layout={layout} onChange={setLayout} />
      </div>

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
            <HeadphonesHint visible={meeting.status === "scheduled"} />
            <div className="flex flex-wrap items-center gap-3 pt-4">
              <Button onClick={session.start} disabled={startDisabled}>
                {t("meetings.session.start")}
              </Button>
              {showEndButton && (
                <Button variant="outline" onClick={session.end}>
                  {t("meetings.session.end")}
                </Button>
              )}
              <CaptureIndicator
                streamStatus={indicatorStreamStatus}
                meDisplayName={meeting.me_display_name}
                counterpartyDisplayName={meeting.counterparty_display_name}
                ending={session.state.phase === "ending"}
              />
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

      {meeting && layout === "columns" ? (
        <div
          data-testid="detail-columns"
          className="grid grid-cols-1 gap-4 lg:grid-cols-[30%_40%_30%] lg:h-[calc(100vh-260px)]"
        >
          <div
            data-testid="detail-pane-playbook"
            className="lg:h-full lg:overflow-y-auto lg:[&>*]:h-full"
          >
            {playbookPane}
          </div>
          <div
            data-testid="detail-pane-transcript"
            className="lg:h-full lg:overflow-y-auto lg:[&>*]:h-full"
          >
            {transcriptPane}
          </div>
          <div
            data-testid="detail-pane-advisor"
            className="lg:h-full lg:overflow-y-auto lg:[&>*]:h-full"
          >
            {advisorPane}
          </div>
        </div>
      ) : (
        meeting && (
          <div data-testid="detail-stack" className="space-y-4">
            <div data-testid="detail-pane-playbook">{playbookPane}</div>
            <div data-testid="detail-pane-transcript">{transcriptPane}</div>
            <div data-testid="detail-pane-advisor">{advisorPane}</div>
          </div>
        )
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
