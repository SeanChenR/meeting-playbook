/**
 * UploadDialog — offline-ingest upload flow (slice-14 task 5.4).
 *
 * Driven by `tus-uploader` for the upload + `offline-ingest-api` for
 * the progress polling. State machine:
 *
 *   idle (file picker + start)
 *     ↓ user clicks Start
 *   uploading (tus progress bar)
 *     ↓ tus onSuccess
 *   polling (transcoding / asr_running)
 *     ↓ progress endpoint state = "completed"
 *   completed → close + invalidate parent meeting query + success toast
 *
 * Any failure transitions to `error`, surfaces the localized message
 * via `localizedErrorMessage`, and re-enables the Start button so the
 * user can pick a different file / retry without re-recording.
 */

import { UploadCloud, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { localizedErrorMessage } from "@/lib/i18n-errors";
import { type OfflineIngestProgress, getOfflineIngestProgress } from "@/lib/offline-ingest-api";
import {
  type OfflineIngestUploadError,
  type UploadHandle,
  uploadOfflineAudio,
} from "@/lib/tus-uploader";
import { type MeetingDetail } from "@/lib/meetings-api";

type DialogState =
  | { kind: "idle" }
  | { kind: "uploading"; percent: number }
  | { kind: "polling"; progress: OfflineIngestProgress }
  | { kind: "error"; errorCode: string };

export interface UploadDialogProps {
  meeting: MeetingDetail;
  open: boolean;
  onClose: () => void;
  /** Polling interval in ms; override in tests for faster runs. */
  pollIntervalMs?: number;
  /** Inject a custom uploader for tests. */
  uploader?: typeof uploadOfflineAudio;
  /** Inject a custom progress fetcher for tests. */
  progressFetcher?: typeof getOfflineIngestProgress;
}

export function UploadDialog({
  meeting,
  open,
  onClose,
  pollIntervalMs = 3000,
  uploader = uploadOfflineAudio,
  progressFetcher = getOfflineIngestProgress,
}: UploadDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [file, setFile] = useState<File | null>(null);
  const [actualStartedAt, setActualStartedAt] = useState<string>(() =>
    _defaultActualStartedAt(meeting),
  );
  const [state, setState] = useState<DialogState>({ kind: "idle" });
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadHandleRef = useRef<UploadHandle | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cancel polling + uploads when the dialog closes externally.
  useEffect(() => {
    if (!open) {
      _clearPollTimer(pollTimerRef);
      uploadHandleRef.current?.abort().catch(() => undefined);
      uploadHandleRef.current = null;
      setState({ kind: "idle" });
      setFile(null);
      setIsDragActive(false);
    }
  }, [open]);

  // ESC closes the dialog when no upload is in flight.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && state.kind !== "uploading" && state.kind !== "polling") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, state.kind, onClose]);

  // Cleanup on unmount.
  useEffect(
    () => () => {
      _clearPollTimer(pollTimerRef);
      uploadHandleRef.current?.abort().catch(() => undefined);
    },
    [],
  );

  if (!open) {
    return null;
  }

  const isStartable = state.kind === "idle" && file !== null && actualStartedAt.length > 0;

  const handleStart = () => {
    if (!file) return;
    setState({ kind: "uploading", percent: 0 });

    uploadHandleRef.current = uploader({
      meetingId: meeting.id,
      file,
      actualStartedAt: new Date(actualStartedAt),
      onProgress: ({ bytesUploaded, bytesTotal }) => {
        const percent = bytesTotal > 0 ? Math.round((bytesUploaded / bytesTotal) * 100) : 0;
        setState({ kind: "uploading", percent });
      },
      onComplete: () => {
        // Start polling for transcoding / ASR state.
        _startPolling({
          meetingId: meeting.id,
          intervalMs: pollIntervalMs,
          progressFetcher,
          pollTimerRef,
          onState: setState,
          onCompleted: () => {
            toast.success(t("offline_ingest.dialog.completed"));
            queryClient.invalidateQueries({ queryKey: ["meeting", meeting.id] });
            // Slice-16 task 10.x bug fix: also invalidate the transcripts
            // query so the new chunks appear in the transcript pane
            // immediately. Without this the user has to reload the page
            // to see the freshly-ingested transcript.
            queryClient.invalidateQueries({ queryKey: ["transcripts", meeting.id] });
            onClose();
          },
        });
      },
      onError: (err: OfflineIngestUploadError) => {
        setState({ kind: "error", errorCode: err.errorCode });
      },
    });
  };

  const handleRetry = () => {
    setState({ kind: "idle" });
  };

  const handleFiles = (files: FileList | null | undefined) => {
    const next = files?.[0];
    if (next) {
      setFile(next);
    }
  };

  const isBusy = state.kind === "uploading" || state.kind === "polling";

  return (
    <div
      data-testid="offline-ingest-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-lg rounded-lg border border-(--color-border) bg-(--color-card) p-6 space-y-4 shadow-xl">
        <header className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-(--color-foreground)">
            {t("offline_ingest.dialog.heading")}
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("offline_ingest.dialog.close")}
            disabled={isBusy}
            onClick={onClose}
            className="-mr-2 -mt-2"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        {state.kind === "idle" || state.kind === "error" ? (
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="offline-ingest-file">{t("offline_ingest.dialog.fileLabel")}</Label>
              <button
                type="button"
                data-testid="offline-ingest-dropzone"
                className={`w-full rounded-md border-2 border-dashed transition-colors px-4 py-8 text-center cursor-pointer ${
                  isDragActive
                    ? "border-(--color-primary) bg-(--color-primary)/5"
                    : "border-(--color-border) hover:border-(--color-primary)/50 hover:bg-(--color-muted)/40"
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDragEnter={(e) => {
                  e.preventDefault();
                  setIsDragActive(true);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!isDragActive) setIsDragActive(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setIsDragActive(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragActive(false);
                  handleFiles(e.dataTransfer?.files);
                }}
              >
                <input
                  ref={fileInputRef}
                  id="offline-ingest-file"
                  type="file"
                  accept=".wav,.mp3,.m4a,.aac,.flac,.ogg,audio/*"
                  className="sr-only"
                  onChange={(e) => handleFiles(e.target.files)}
                />
                <UploadCloud className="mx-auto h-8 w-8 text-(--color-muted-foreground) mb-2" />
                <p className="text-sm font-medium text-(--color-foreground)">
                  {isDragActive
                    ? t("offline_ingest.dialog.dropzoneActive")
                    : t("offline_ingest.dialog.dropzoneHint")}
                </p>
                <p className="text-xs text-(--color-muted-foreground) mt-1">
                  {t("offline_ingest.dialog.dropzoneFormats")}
                </p>
              </button>
              {file ? (
                <div className="flex items-center justify-between rounded-md bg-(--color-muted)/40 px-3 py-2 text-sm">
                  <span className="truncate text-(--color-foreground)">
                    {t("offline_ingest.dialog.selectedFile", {
                      name: file.name,
                      size: _formatBytes(file.size),
                    })}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    {t("offline_ingest.dialog.clearFile")}
                  </Button>
                </div>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label htmlFor="offline-ingest-started-at">
                {t("offline_ingest.dialog.actualStartedAtLabel")}
              </Label>
              <Input
                id="offline-ingest-started-at"
                type="datetime-local"
                value={actualStartedAt}
                onChange={(e) => setActualStartedAt(e.target.value)}
              />
              <p className="text-xs text-(--color-muted-foreground)">
                {t("offline_ingest.dialog.actualStartedAtHint")}
              </p>
            </div>
            {state.kind === "error" ? (
              <div
                role="alert"
                className="rounded-md border border-(--color-destructive)/30 bg-(--color-destructive)/10 px-3 py-2 text-sm text-(--color-destructive)"
              >
                <p className="font-medium">{t("offline_ingest.dialog.errorHeading")}</p>
                <p>{localizedErrorMessage(state.errorCode, t)}</p>
              </div>
            ) : null}
          </div>
        ) : null}

        {state.kind === "uploading" ? (
          <div data-testid="upload-progress" className="space-y-2">
            <p className="text-sm">
              {t("offline_ingest.dialog.uploading", { percent: state.percent })}
            </p>
            <div className="h-2 w-full overflow-hidden rounded bg-(--color-muted)">
              <div
                className="h-full bg-(--color-primary) transition-[width] duration-150"
                style={{ width: `${state.percent}%` }}
              />
            </div>
          </div>
        ) : null}

        {state.kind === "polling" ? (
          <div data-testid="ingest-progress" className="space-y-1 text-sm">
            {state.progress.state === "transcoding" ? (
              <p>{t("offline_ingest.dialog.transcoding")}</p>
            ) : null}
            {state.progress.state === "asr_running" ? (
              <p>
                {t("offline_ingest.dialog.asrRunning", {
                  processed: state.progress.chunks_processed ?? 0,
                  total: state.progress.chunks_total ?? 0,
                })}
              </p>
            ) : null}
            {state.progress.state === "failed" ? (
              <p role="alert" className="text-(--color-destructive)">
                {localizedErrorMessage(state.progress.error_code ?? "offline_ingest.network", t)}
              </p>
            ) : null}
          </div>
        ) : null}

        <footer className="flex justify-end gap-2">
          {state.kind === "idle" || state.kind === "error" ? (
            <>
              <Button variant="ghost" onClick={onClose}>
                {t("offline_ingest.dialog.cancel")}
              </Button>
              {state.kind === "error" ? (
                <Button onClick={handleRetry}>{t("common.retry") || "Retry"}</Button>
              ) : (
                <Button onClick={handleStart} disabled={!isStartable}>
                  {t("offline_ingest.dialog.startButton")}
                </Button>
              )}
            </>
          ) : null}
        </footer>
      </div>
    </div>
  );
}

function _defaultActualStartedAt(meeting: MeetingDetail): string {
  // `datetime-local` wants `yyyy-MM-ddTHH:mm`; if the meeting has a
  // scheduled start, format it; otherwise fall back to `now()` so the
  // input is never empty.
  const source = meeting.scheduled_start_at ?? new Date().toISOString();
  return source.slice(0, 16);
}

function _formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function _clearPollTimer(ref: { current: ReturnType<typeof setInterval> | null }) {
  if (ref.current !== null) {
    clearInterval(ref.current);
    ref.current = null;
  }
}

function _startPolling(args: {
  meetingId: string;
  intervalMs: number;
  progressFetcher: typeof getOfflineIngestProgress;
  pollTimerRef: { current: ReturnType<typeof setInterval> | null };
  onState: (state: DialogState) => void;
  onCompleted: () => void;
}): void {
  const tick = async () => {
    try {
      const progress = await args.progressFetcher(args.meetingId);
      if (progress.state === "completed") {
        _clearPollTimer(args.pollTimerRef);
        args.onCompleted();
        return;
      }
      if (progress.state === "failed") {
        _clearPollTimer(args.pollTimerRef);
        args.onState({
          kind: "error",
          errorCode: progress.error_code ?? "offline_ingest.network",
        });
        return;
      }
      args.onState({ kind: "polling", progress });
    } catch (err) {
      _clearPollTimer(args.pollTimerRef);
      const errorCode =
        err && typeof err === "object" && "errorCode" in err
          ? String((err as { errorCode: string }).errorCode)
          : "offline_ingest.network";
      args.onState({ kind: "error", errorCode });
    }
  };

  // Kick once immediately so users don't wait for the first interval.
  void tick();
  args.pollTimerRef.current = setInterval(tick, args.intervalMs);
}
