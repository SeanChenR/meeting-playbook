/**
 * MeetingDetail route — slice ui-overhaul-claude-design tasks 5.1 + 5.6.
 *
 * Structure aligned with design bundle `MeetingDetailScreen`:
 *   <ProtectedShell fullBleed>
 *     <div max-w-[1440px] mx-auto px-6 pt-5 ...>
 *       <BackLink to="/meetings" />
 *       <MetadataCard ... />                      ← extracted (task 5.2)
 *       <div tabs row>
 *         <Tabs>工作區 / 摘要</Tabs>
 *         <LayoutSwitcher />                      ← only on workspace tab
 *       </div>
 *       <AnimatePresence mode="wait">             ← task 5.6 cross-fade
 *         workspace ? <Workspace />               ← task 5.5
 *                   : <SummaryPane />
 *       </AnimatePresence>
 *     </div>
 *   </ProtectedShell>
 *
 * The Workspace tab content uses framer-motion `AnimatePresence` with the
 * `tabContent` preset (100ms exit / 150ms enter cross-fade); the summary
 * tab is disabled via radix `disabled` until status === "completed".
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvisorPane } from "../../components/advisor-pane";
import { AttachmentDropzone } from "../../components/attachment-dropzone";
import { AsrProviderSelector } from "../../components/asr-provider-selector";
import { CaptureIndicator } from "../../components/capture-indicator";
import { HeadphonesHint } from "../../components/headphones-hint";
import { LayoutSwitcher } from "../../components/layout-switcher";
import { Upload } from "lucide-react";
import { MeetingAudioMiniPlayer } from "../../components/meeting-audio-mini-player";
import { miniPlayerStore } from "../../hooks/use-mini-player";
import { MeetingEditForm } from "../../components/meeting-edit-form";
import { MetadataCard } from "../../components/metadata-card";
import { UploadDialog } from "../../components/offline-ingest/UploadDialog";
import { Button } from "../../components/ui/button";
import { PlaybookPane } from "../../components/playbook-pane";
import { ProtectedShell } from "../../components/protected-shell";
import { RerunButton } from "../../components/rerun-button";
import { SummaryPane } from "../../components/summary-pane";
import { TagChip } from "../../components/tags/tag-chip";
import { TagPicker } from "../../components/tags/tag-picker";
import { TranscriptPane } from "../../components/transcript-pane";
import { Workspace } from "../../components/workspace";
import { Alert } from "../../components/ui/alert";
import { AlertDialog } from "../../components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { useDetailLayout } from "../../hooks/use-detail-layout";
import { useDetailTab } from "../../hooks/use-detail-tab";
import { useMeetingSession } from "../../hooks/use-meeting-session";
import { chatMessagesQueryOptions } from "../../lib/chat-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { tabContent } from "../../lib/motion-presets";
import {
  meetingQueryOptions,
  MeetingApiError,
  useDeleteMeetingMutation,
} from "../../lib/meetings-api";
import { rowToMessage, transcriptChunksQueryOptions } from "../../lib/transcripts-api";

export function MeetingDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams({ strict: false }) as { id?: string };
  const meetingId = id ?? "";

  const query = useQuery({ ...meetingQueryOptions(meetingId), enabled: !!meetingId });
  const deleteMutation = useDeleteMeetingMutation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [offlineIngestOpen, setOfflineIngestOpen] = useState(false);
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Slice-20a: collapsible Attachments section. Default expanded; the
  // collapsed/expanded choice is persisted to localStorage so a reload
  // (or layout switch) doesn't reset it.
  const [attachmentsExpanded, setAttachmentsExpanded] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const v = window.localStorage.getItem("meeting-detail.attachments-expanded");
    return v === null ? true : v === "true";
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("meeting-detail.attachments-expanded", String(attachmentsExpanded));
  }, [attachmentsExpanded]);
  const [layout, setLayout] = useDetailLayout();

  const meeting = query.data ?? null;
  const session = useMeetingSession(meetingId);

  // Slice-15 task 8.5: needs_recording cards link here with
  // ?action=upload. Auto-open the upload dialog on mount and scrub
  // the query so a subsequent reload doesn't re-fire.
  const search = useSearch({ strict: false }) as { action?: string };
  useEffect(() => {
    if (search.action !== "upload") return;
    setOfflineIngestOpen(true);
    navigate({ search: { action: undefined } as never, replace: true });
  }, [search.action, navigate]);
  const queryClient = useQueryClient();
  const reducedMotion = useReducedMotion();

  // Slice-9: hydrate persisted chat history + invalidate cache on advice_done.
  const chatMessagesQuery = useQuery(chatMessagesQueryOptions(meetingId, !!meetingId));
  useEffect(() => {
    if (Array.isArray(chatMessagesQuery.data)) {
      session.loadHistory(chatMessagesQuery.data);
    }
  }, [chatMessagesQuery.data, session]);
  useEffect(() => {
    session.onAdviceDone = () => {
      queryClient.invalidateQueries({ queryKey: ["chat_messages", meetingId] });
    };
    return () => {
      session.onAdviceDone = null;
    };
  }, [session, queryClient, meetingId]);

  // Slice-10: invalidate meeting cache when WS reaches `ended` so the
  // status flips to "completed" and the Summary tab unlocks.
  useEffect(() => {
    if (session.state.phase === "ended") {
      queryClient.invalidateQueries({ queryKey: ["meetings", meetingId] });
    }
  }, [session.state.phase, queryClient, meetingId]);

  // Slice-7: per-stream indicator state. Hidden outside in-progress / ending.
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

  // Slice-16 task 10.7: populate the mini-player store whenever the
  // meeting's chunks + recordings are loaded. `chunks_sorted` and
  // `recordings` drive `seekToChunk` + `pickMeetingRecording` so the
  // bottom player can play the whole me-stream WAV and chunk action
  // menu "Play this chunk" can compute seek offsets.
  useEffect(() => {
    if (!meetingId || meeting === null) return;
    miniPlayerStore.setContext({
      meeting_id: meetingId,
      chunks: sessionChunks.map((c, idx) => ({
        id: c.id ?? `${c.started_at}-${c.speaker}-${idx}`,
        speaker: c.speaker,
        started_at: c.started_at,
        ended_at: c.ended_at,
      })),
      recordings: meeting.recordings ?? [],
    });
  }, [meetingId, meeting, sessionChunks]);
  const sessionError =
    session.state.phase === "error" ? localizedErrorMessage(session.state.errorCode, t) : null;
  const startDisabled =
    !meeting ||
    meeting.status !== "scheduled" ||
    session.state.phase === "connecting" ||
    session.state.phase === "in_progress" ||
    session.state.phase === "ending";

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

  // Three workspace panes — built once, layout-agnostic.
  const playbookPane = meeting && <PlaybookPane meetingId={meetingId} />;
  const transcriptPane = meeting && (
    <TranscriptPane
      chunks={sessionChunks}
      meDisplayName={meeting.me_display_name}
      counterpartyDisplayName={meeting.counterparty_display_name}
      meetingId={meetingId}
      rerunPending={Boolean(meeting.rerun_asr_pending)}
    />
  );
  const advisorPane = meeting && (
    <AdvisorPane session={session} meDisplayName={meeting.me_display_name} />
  );

  return (
    <ProtectedShell fullBleed>
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-6 pt-5">
        {/* Slice meetings-ux-revamp task 5.2: standalone BackLink row
            removed — BackLink now lives inside MetadataCard's prev/next nav. */}
        {error && <Alert variant="destructive">{error}</Alert>}

        {meeting === null && !error && (
          <p className="text-sm text-(--color-muted-foreground)">{t("common.loading")}</p>
        )}

        {meeting && (
          <MetadataCard
            meeting={meeting}
            phase={session.state.phase}
            onStart={session.start}
            onEnd={session.end}
            startDisabled={startDisabled}
            onDelete={() => setConfirmOpen(true)}
            asrSelector={<AsrProviderSelector meeting={meeting} />}
            captureIndicator={
              <CaptureIndicator
                streamStatus={indicatorStreamStatus}
                meDisplayName={meeting.me_display_name}
                counterpartyDisplayName={meeting.counterparty_display_name}
                ending={session.state.phase === "ending"}
              />
            }
            rerunSlot={<RerunButton meeting={meeting} />}
            uploadSlot={
              <Button
                type="button"
                size="sm"
                variant={meeting.status === "completed" ? "secondary" : "outline"}
                disabled={meeting.status === "in_progress"}
                onClick={() => setOfflineIngestOpen(true)}
                data-testid="metadata-upload-audio"
              >
                <Upload className="size-3.5" />
                {t("meetings.session.uploadAudio")}
              </Button>
            }
          />
        )}

        {meeting && (
          <div data-testid="meeting-detail-tags-row" className="flex flex-wrap items-center gap-2">
            {(meeting.tags ?? []).map((tag) => (
              <TagChip key={tag.id} name={tag.name} color={tag.color} />
            ))}
            <TagPicker meetingId={meeting.id} currentTags={meeting.tags ?? []} />
          </div>
        )}

        {meeting && (
          <UploadDialog
            meeting={meeting}
            open={offlineIngestOpen}
            onClose={() => setOfflineIngestOpen(false)}
          />
        )}

        {meeting && (
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              data-testid="meeting-edit-toggle"
              onClick={() => setEditFormOpen((v) => !v)}
              className="rounded-md border border-(--color-border) px-3 py-1.5 text-xs hover:bg-(--color-muted)/40"
            >
              {editFormOpen ? t("meetings.edit.cancel") : t("meetings.edit.editToggle")}
            </button>
          </div>
        )}

        {meeting && (
          <section
            data-testid="meeting-detail-attachments-section"
            data-expanded={attachmentsExpanded}
            className="rounded-md border border-(--color-border) bg-(--color-card)"
          >
            <button
              type="button"
              data-testid="meeting-detail-attachments-toggle"
              aria-expanded={attachmentsExpanded}
              onClick={() => setAttachmentsExpanded((v) => !v)}
              className="flex w-full items-center justify-between px-4 py-2 text-sm font-semibold text-(--color-foreground) hover:bg-(--color-muted)/40"
            >
              <span>{t("attachments.heading")}</span>
              <span aria-hidden className="text-xs text-(--color-muted-foreground)">
                {attachmentsExpanded ? "−" : "+"}
              </span>
            </button>
            {attachmentsExpanded && (
              <div className="border-t border-(--color-border) p-4">
                <AttachmentDropzone meetingId={meetingId} />
              </div>
            )}
          </section>
        )}

        {meeting && (
          <Dialog open={editFormOpen} onOpenChange={setEditFormOpen}>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{t("meetings.edit.dialogTitle")}</DialogTitle>
                <DialogDescription>{t("meetings.edit.dialogDescription")}</DialogDescription>
              </DialogHeader>
              <MeetingEditForm
                meeting={meeting}
                onSaved={() => setEditFormOpen(false)}
                onCancel={() => setEditFormOpen(false)}
              />
            </DialogContent>
          </Dialog>
        )}

        {meeting && <HeadphonesHint visible={meeting.status === "scheduled"} />}
        {sessionError && <Alert variant="destructive">{sessionError}</Alert>}

        {meeting && (
          <DetailTabsView
            meeting={meeting}
            meetingId={meetingId}
            layout={layout}
            onLayoutChange={setLayout}
            playbookPane={playbookPane}
            transcriptPane={transcriptPane}
            advisorPane={advisorPane}
            reducedMotion={!!reducedMotion}
          />
        )}
      </div>

      {/* Slice-16: sticky bottom mini-player for chunk-level audio playback.
          Mounted once at the page root so it survives tab switching between
          Workspace and Summary, and uses the module-scoped store so
          TranscriptChunkRow ▶ clicks update without prop drilling. */}
      {meeting && <MeetingAudioMiniPlayer meetingId={meetingId} />}

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

interface DetailTabsViewProps {
  meeting: { title: string; created_at: string; status: string };
  meetingId: string;
  layout: "columns" | "stack";
  onLayoutChange: (next: "columns" | "stack") => void;
  playbookPane: React.ReactNode;
  transcriptPane: React.ReactNode;
  advisorPane: React.ReactNode;
  reducedMotion: boolean;
}

function DetailTabsView({
  meeting,
  meetingId,
  layout,
  onLayoutChange,
  playbookPane,
  transcriptPane,
  advisorPane,
  reducedMotion,
}: DetailTabsViewProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useDetailTab(meetingId, meeting);
  const summaryEnabled = meeting.status === "completed";

  // Reduced motion → 0-duration cross-fade so the swap is instant but the
  // AnimatePresence node tree stays consistent.
  const motionTransition = reducedMotion ? { duration: 0 } : undefined;

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as "workspace" | "summary")}>
      <div className="flex items-center justify-between gap-3">
        <TabsList className="h-9">
          <TabsTrigger value="workspace" data-testid="detail-tab-workspace">
            {t("meetings.detail.tabs.workspace")}
          </TabsTrigger>
          <TabsTrigger
            value="summary"
            disabled={!summaryEnabled}
            title={!summaryEnabled ? t("meetings.summary.disabledHint") : undefined}
            data-testid="detail-tab-summary"
          >
            {t("meetings.detail.tabs.summary")}
          </TabsTrigger>
        </TabsList>
        {tab === "workspace" && (
          <div data-testid="detail-layout-switcher-slot">
            <LayoutSwitcher layout={layout} onChange={onLayoutChange} />
          </div>
        )}
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {tab === "workspace" ? (
          <motion.div
            key="workspace"
            data-testid="detail-tab-panel-workspace"
            variants={tabContent}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={motionTransition}
            className="mt-4"
          >
            <Workspace
              layout={layout}
              playbook={
                <div data-testid="detail-pane-playbook" className="h-full min-w-0">
                  {playbookPane}
                </div>
              }
              transcript={
                <div data-testid="detail-pane-transcript" className="h-full min-w-0">
                  {transcriptPane}
                </div>
              }
              advisor={
                <div data-testid="detail-pane-advisor" className="h-full min-w-0">
                  {advisorPane}
                </div>
              }
            />
          </motion.div>
        ) : (
          summaryEnabled && (
            <motion.div
              key="summary"
              data-testid="detail-tab-panel-summary"
              variants={tabContent}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={motionTransition}
              className="mt-4"
            >
              <SummaryPane meetingId={meetingId} meeting={meeting} />
            </motion.div>
          )
        )}
      </AnimatePresence>
    </Tabs>
  );
}
