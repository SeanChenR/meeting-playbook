/**
 * MeetingDetail route — refactor-meeting-detail-three-column.
 *
 * Visual order top-to-bottom:
 *   <ProtectedShell fullBleed>
 *     {AsrLoadingDialog}                          ← overlay, mounted always
 *     <topStackRef>                                ← measured for column height var
 *       <MeetingPrevNextNav>                       ← back link + prev/next
 *       <MeetingHeaderBar menuTrigger={…}>         ← title + meta + actions
 *       {HeadphonesHint?}                          ← dual+idle+scheduled
 *       {sessionError?}
 *       <Tabs>工作區 / 摘要</Tabs>
 *     </topStackRef>
 *     <main>                                       ← tab panels
 *       workspace → <Workspace> 3 cols
 *       summary   → <MeetingDetailSummaryView> 2 cols
 *     </main>
 *     <MeetingAudioMiniPlayer/>                    ← sticky bottom
 *     <SuccessResultOverlay open={upload|export}/>
 *     {6 dialogs/popovers triggered by overflow menu}
 *   </ProtectedShell>
 *
 * No MetadataCard. No LayoutSwitcher. No inline tags row / attachment section
 * / edit toggle button — all moved into the ⋯ overflow menu dialogs.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Lock } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvisorPane } from "../../components/advisor-pane";
import { ShineBorder } from "../../components/magicui/shine-border";
import { MeetingDetailActionBar } from "../../components/meeting-detail-action-bar";
import { AsrLoadingDialog } from "../../components/asr-loading-dialog";
import { AsrProviderSelector } from "../../components/asr-provider-selector";
import { AttachmentDropzone } from "../../components/attachment-dropzone";
import { CaptureIndicator } from "../../components/capture-indicator";
import { MeetingAudioMiniPlayer } from "../../components/meeting-audio-mini-player";
import { miniPlayerStore } from "../../hooks/use-mini-player";
import { MeetingDetailSummaryView } from "../../components/meeting-detail-summary-view";
import { MeetingEditForm } from "../../components/meeting-edit-form";
import { MeetingHeaderBar } from "../../components/meeting-header-bar";
import { MeetingLinksSection } from "../../components/meeting-links-section";
import { MeetingPrevNextNav } from "../../components/meeting-prev-next-nav";
import { RecordingModeSelector } from "../../components/recording-mode-selector";
import { UploadDialog } from "../../components/offline-ingest/UploadDialog";
import { PlaybookPane } from "../../components/playbook-pane";
import { ProtectedShell } from "../../components/protected-shell";
import { SuccessResultOverlay } from "../../components/success-result-overlay";
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
import { useDetailTab } from "../../hooks/use-detail-tab";
import { useMeetingSession } from "../../hooks/use-meeting-session";
import { chatMessagesQueryOptions } from "../../lib/chat-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { tabContent } from "../../lib/motion-presets";
import {
  meetingQueryOptions,
  MeetingApiError,
  useDeleteMeetingMutation,
  usePatchMeetingMutation,
} from "../../lib/meetings-api";
import { resolveMeetingBucket } from "../../lib/meetings-bucket";
import { listAttachments } from "../../lib/attachments-api";
import { meetingLinksQueryOptions } from "../../lib/meeting-links-api";
import { rowToMessage, transcriptChunksQueryOptions } from "../../lib/transcripts-api";

export function MeetingDetail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams({ strict: false }) as { id?: string };
  const meetingId = id ?? "";

  const query = useQuery({ ...meetingQueryOptions(meetingId), enabled: !!meetingId });
  const deleteMutation = useDeleteMeetingMutation();

  // Dialog state — every secondary affordance opens from the ⋯ menu.
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [offlineIngestOpen, setOfflineIngestOpen] = useState(false);
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [tagsDialogOpen, setTagsDialogOpen] = useState(false);
  const [attachmentsDialogOpen, setAttachmentsDialogOpen] = useState(false);
  const [linkedDialogOpen, setLinkedDialogOpen] = useState(false);
  const [asrDialogOpen, setAsrDialogOpen] = useState(false);
  const [modeDialogOpen, setModeDialogOpen] = useState(false);
  const [uploadSuccessOpen, setUploadSuccessOpen] = useState(false);
  const [exportSuccessOpen, setExportSuccessOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const meeting = query.data ?? null;
  const session = useMeetingSession(meetingId);

  // Slice-15 task 8.5: needs_recording cards link here with ?action=upload.
  const search = useSearch({ strict: false }) as { action?: string };
  useEffect(() => {
    if (search.action !== "upload") return;
    setOfflineIngestOpen(true);
    navigate({ search: { action: undefined } as never, replace: true });
  }, [search.action, navigate]);
  const queryClient = useQueryClient();
  const reducedMotion = useReducedMotion();

  // Hydrate persisted chat history + invalidate cache on advice_done.
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

  // Mini-player wiring (slice-16 task 10.7).
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
  const bucket = meeting ? resolveMeetingBucket(meeting) : null;
  // Inline ASR provider switch wired by the action-bar dropdown — bypasses
  // the prior dialog flow per Sean's "直接下拉中顯示選項就好" feedback.
  const patchAsrMutation = usePatchMeetingMutation(meetingId);
  // Per Sean: meta-strip count chips were stuck at 0 because the prior code
  // looked them up on the meeting payload (which doesn't carry them). The
  // real data lives in dedicated queries — pull the counts inline here.
  const attachmentsQuery = useQuery({
    queryKey: ["meeting-attachments", meetingId],
    queryFn: () => listAttachments(meetingId),
    enabled: !!meetingId,
  });
  const linksQuery = useQuery({
    ...meetingLinksQueryOptions(meetingId),
    enabled: !!meetingId,
  });
  const attachmentsCount = attachmentsQuery.data?.length ?? 0;
  const linksCount = linksQuery.data?.length ?? 0;
  const startDisabled =
    !meeting ||
    bucket !== "upcoming" ||
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

  // refactor task 5.1: measure top-stack height + mini-player height, inject
  // as CSS variables so each MeetingColumn can compute calc(100vh - …) safely.
  const topStackRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  useLayoutEffect(() => {
    const top = topStackRef.current;
    const container = containerRef.current;
    if (!top || !container) return;
    let raf = 0;
    const update = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const topH = top.getBoundingClientRect().height;
        // Claude Design alignment: previously deducted 60px (mini player) +
        // 24px buffer unconditionally → columns ended up short on screens
        // where the player isn't rendered. Detect the actual mini player
        // node and only deduct when it's mounted; tighten the gutter to
        // 16px so columns gain visible vertical space.
        const playerNode = container.querySelector<HTMLElement>(
          '[data-testid="recording-mini-player"]',
        );
        const playerH = playerNode ? playerNode.getBoundingClientRect().height : 0;
        // Guarantee a generous minimum (78vh) so even when the top stack is
        // tall (header bar + meta strip + hint + tabs), the workspace doesn't
        // feel cramped. The visible value is whichever is larger.
        container.style.setProperty(
          "--detail-column-h",
          `max(calc(100vh - ${Math.ceil(topH)}px - ${Math.ceil(playerH)}px - 8px), 78vh)`,
        );
      });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(top);
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [meeting, sessionError, session.state.phase, session.state.mode]);

  // Lifted tab state — both Tabs trigger row and content panel SHALL read the
  // same source of truth. Previously each had its own useDetailTab(), so
  // clicking the summary tab in the bar didn't update the content panel.
  const [detailTab, setDetailTab] = useDetailTab(meetingId, meeting);

  // Mode card editability gate (matches the prior ⋯-menu visibility — the
  // action bar only lets users open the mode dialog when it's actionable).
  const showModeMenuItem =
    !!meeting && meeting.status === "scheduled" && session.state.phase === "idle";

  return (
    <ProtectedShell fullBleed>
      <AsrLoadingDialog phase={session.state.phase as never} />

      <div
        ref={containerRef}
        className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-6 pt-5"
      >
        {/* Top stack — measured for --detail-column-h injection */}
        <div ref={topStackRef} className="flex flex-col gap-4">
          <MeetingPrevNextNav currentId={meetingId} />

          {error && <Alert variant="destructive">{error}</Alert>}

          {meeting === null && !error && (
            <p className="text-sm text-(--color-muted-foreground)">{t("common.loading")}</p>
          )}

          {meeting && (
            <MeetingHeaderBar
              meeting={meeting}
              phase={session.state.phase as never}
              captureIndicator={
                <CaptureIndicator
                  streamStatus={indicatorStreamStatus}
                  meDisplayName={meeting.me_display_name}
                  counterpartyDisplayName={meeting.counterparty_display_name}
                  ending={session.state.phase === "ending"}
                  chunks={liveChunks}
                />
              }
              onTagsOpen={() => setTagsDialogOpen(true)}
            />
          )}

          {meeting && bucket && (
            <MeetingDetailActionBar
              bucket={bucket}
              phase={session.state.phase as never}
              startDisabled={startDisabled}
              onStart={session.start}
              onEnd={session.end}
              onEdit={() => setEditFormOpen(true)}
              onUpload={() => setOfflineIngestOpen(true)}
              onDelete={() => setConfirmOpen(true)}
              meeting={meeting}
              meetingTitle={meeting.title}
              scheduledStartAt={meeting.scheduled_start_at}
              onExportSuccess={() => setExportSuccessOpen(true)}
              attachmentsCount={attachmentsCount}
              linksCount={linksCount}
              onAttachmentsOpen={() => setAttachmentsDialogOpen(true)}
              onLinkedOpen={() => setLinkedDialogOpen(true)}
              recordingMode={session.state.mode ?? "dual"}
              asrProvider={meeting.asr_provider}
              onRecordingModeChange={showModeMenuItem ? session.setMode : undefined}
              onAsrProviderChange={(provider) =>
                patchAsrMutation.mutate({ asr_provider: provider })
              }
            />
          )}

          {sessionError && <Alert variant="destructive">{sessionError}</Alert>}
        </div>

        {/* Workspace / Summary section — wraps the Tabs + content under one
            chrome so the tabs don't feel like a floating widget per Sean's
            "下面也用大的 Section 把工作區和摘要包起來" feedback. */}
        {meeting && (
          <section
            data-testid="meeting-detail-content-section"
            className="relative overflow-hidden rounded-2xl bg-(--color-surface) shadow-(--shadow-sm) ring-1 ring-(--color-border)/60"
          >
            <ShineBorder duration={18} />
            <div className="relative z-[1] flex flex-col gap-4 p-4">
              <div className="flex justify-center">
                <DetailTabsBar
                  meetingId={meetingId}
                  meeting={meeting}
                  tab={detailTab}
                  onTabChange={setDetailTab}
                />
              </div>
              <DetailTabsContent
                tab={detailTab}
                meeting={meeting}
                meetingId={meetingId}
                playbookPane={<PlaybookPane meetingId={meetingId} />}
                transcriptPane={
                  <TranscriptPane
                    chunks={sessionChunks}
                    meDisplayName={meeting.me_display_name}
                    counterpartyDisplayName={meeting.counterparty_display_name}
                    meetingId={meetingId}
                    rerunPending={Boolean(meeting.rerun_asr_pending)}
                    noAudioAvailable={bucket === "completed" && !meeting.recordings_available}
                  />
                }
                advisorPane={
                  <AdvisorPane session={session} meDisplayName={meeting.me_display_name} />
                }
                reducedMotion={!!reducedMotion}
              />
            </div>
          </section>
        )}
      </div>

      {/* Sticky bottom mini-player — survives tab switching */}
      {meeting && <MeetingAudioMiniPlayer meetingId={meetingId} />}

      {/* Success overlays — upload + export */}
      <SuccessResultOverlay
        open={uploadSuccessOpen}
        title={t("meetings.detail.uploadSuccessTitle")}
        subtitle={t("meetings.detail.uploadSuccessSubtitle")}
        autoDismissMs={3000}
        onClose={() => setUploadSuccessOpen(false)}
        primaryAction={{
          label: t("meetings.detail.viewTranscript"),
          onClick: () => {
            // best-effort focus: scroll to transcript column
            document
              .querySelector('[data-testid="meeting-column-transcript"]')
              ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
          },
        }}
      />
      <SuccessResultOverlay
        open={exportSuccessOpen}
        title={t("meetings.detail.exportSuccessTitle")}
        subtitle={t("meetings.detail.exportSuccessSubtitle")}
        autoDismissMs={3000}
        onClose={() => setExportSuccessOpen(false)}
      />

      {/* Dialogs / popovers triggered by the ⋯ menu */}
      {meeting && (
        <UploadDialog
          meeting={meeting}
          open={offlineIngestOpen}
          onClose={() => setOfflineIngestOpen(false)}
          onUploadSuccess={() => setUploadSuccessOpen(true)}
        />
      )}

      <Dialog open={editFormOpen} onOpenChange={setEditFormOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("meetings.edit.dialogTitle")}</DialogTitle>
            <DialogDescription>{t("meetings.edit.dialogDescription")}</DialogDescription>
          </DialogHeader>
          {meeting && (
            <MeetingEditForm
              meeting={meeting}
              onSaved={() => setEditFormOpen(false)}
              onCancel={() => setEditFormOpen(false)}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={tagsDialogOpen} onOpenChange={setTagsDialogOpen}>
        <DialogContent data-testid="meeting-tags-dialog" className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("meetings.detail.menu.tags")}</DialogTitle>
          </DialogHeader>
          {meeting && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {(meeting.tags ?? []).map((tag) => (
                  <TagChip key={tag.id} name={tag.name} color={tag.color} />
                ))}
              </div>
              <TagPicker meetingId={meeting.id} currentTags={meeting.tags ?? []} />
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={attachmentsDialogOpen} onOpenChange={setAttachmentsDialogOpen}>
        <DialogContent data-testid="meeting-attachments-dialog" className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("meetings.detail.menu.attachments")}</DialogTitle>
          </DialogHeader>
          {meeting && <AttachmentDropzone meetingId={meetingId} />}
        </DialogContent>
      </Dialog>

      <Dialog open={linkedDialogOpen} onOpenChange={setLinkedDialogOpen}>
        <DialogContent data-testid="meeting-linked-dialog" className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("meetings.detail.menu.linked")}</DialogTitle>
          </DialogHeader>
          {meeting && <MeetingLinksSection meetingId={meeting.id} />}
        </DialogContent>
      </Dialog>

      <Dialog open={asrDialogOpen} onOpenChange={setAsrDialogOpen}>
        <DialogContent data-testid="meeting-asr-dialog" className="max-w-md">
          <DialogHeader>
            <DialogTitle>ASR 引擎</DialogTitle>
            <DialogDescription>切換下一場會議生效</DialogDescription>
          </DialogHeader>
          {meeting && <AsrProviderSelector meeting={meeting} />}
        </DialogContent>
      </Dialog>

      <Dialog open={modeDialogOpen} onOpenChange={setModeDialogOpen}>
        <DialogContent data-testid="meeting-mode-dialog" className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("meetings.detail.menu.mode")}</DialogTitle>
          </DialogHeader>
          <RecordingModeSelector value={session.state.mode} onChange={session.setMode} />
        </DialogContent>
      </Dialog>

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

interface DetailTabsBarProps {
  meeting: { title: string; created_at: string; status: string };
  meetingId: string;
  tab: "workspace" | "summary";
  onTabChange: (next: "workspace" | "summary") => void;
}

function DetailTabsBar({ meeting, tab, onTabChange }: DetailTabsBarProps) {
  const { t } = useTranslation();
  const setTab = onTabChange;
  // Sean (round 5): non-completed meetings must REALLY disable the summary
  // tab — unclickable, not just visually dimmed. The locked panel inside
  // is still kept as a defensive landing for users who arrive with a
  // ?tab=summary URL parameter.
  const summaryDisabled = meeting.status !== "completed";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as "workspace" | "summary")}
        variant="underline"
      >
        <TabsList className="h-10">
          <TabsTrigger value="workspace" data-testid="detail-tab-workspace">
            {t("meetings.detail.tabs.workspace")}
          </TabsTrigger>
          <TabsTrigger
            value="summary"
            data-testid="detail-tab-summary"
            disabled={summaryDisabled}
            title={summaryDisabled ? t("meetings.summary.lockedTabHint") : undefined}
            className={summaryDisabled ? "inline-flex items-center gap-1" : undefined}
          >
            {summaryDisabled && <Lock className="size-3" strokeWidth={1.8} aria-hidden />}
            {t("meetings.detail.tabs.summary")}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {summaryDisabled && (
        <span
          data-testid="detail-tab-summary-hint"
          className="text-[12px] text-(--color-muted-foreground)"
        >
          {t("meetings.summary.lockedTabHint")}
        </span>
      )}
    </div>
  );
}

interface DetailTabsContentProps {
  meeting: { title: string; created_at: string; status: string };
  meetingId: string;
  tab: "workspace" | "summary";
  playbookPane: React.ReactNode;
  transcriptPane: React.ReactNode;
  advisorPane: React.ReactNode;
  reducedMotion: boolean;
}

function DetailTabsContent({
  meeting,
  meetingId,
  tab,
  playbookPane,
  transcriptPane,
  advisorPane,
  reducedMotion,
}: DetailTabsContentProps) {
  const summaryEnabled = meeting.status === "completed";
  const motionTransition = reducedMotion ? { duration: 0 } : undefined;

  return (
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
          className="mt-2"
        >
          <Workspace playbook={playbookPane} transcript={transcriptPane} advisor={advisorPane} />
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
            className="mt-2"
          >
            <MeetingDetailSummaryView meetingId={meetingId} meeting={meeting} />
          </motion.div>
        )
      )}
    </AnimatePresence>
  );
}
