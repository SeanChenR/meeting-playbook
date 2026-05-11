/**
 * TranscriptPane — chronological transcript chunks for a meeting session.
 *
 * Per spec meeting-session ADDED requirement "TranscriptPane renders chunks
 * with the meeting's me display name". For slice-6 every chunk has
 * `speaker = "me"`; the layout already accommodates a future "counterparty"
 * speaker (slice-7) by reading `chunk.speaker` and tagging via data attribute
 * for CSS targeting.
 *
 * Slice-11: when the parent's meeting has `rerun_asr_pending === true` we
 * poll GET /api/meetings/{id}/rerun_asr_status every 1s and overlay a
 * skeleton + progress counter. On the pending→idle transition we invalidate
 * the transcript cache so the new content swaps in immediately.
 *
 * NO emojis (per UI feedback memory). Visual polish comes in the UI overhaul.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { TranscriptChunkMessage } from "../lib/session-ws";
import {
  isRerunPending,
  rerunStatusQueryOptions,
  useTranscriptInvalidationOnRerunComplete,
} from "../lib/rerun-api";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "../lib/utils";

interface TranscriptPaneProps {
  chunks: TranscriptChunkMessage[];
  meDisplayName: string;
  counterpartyDisplayName: string;
  /** Slice-11: meeting id for the rerun-status polling query (optional —
   *  pre-slice-11 callers may omit). */
  meetingId?: string;
  /** Slice-11: drives the overlay + enables the polling query when true. */
  rerunPending?: boolean;
}

function _speakerLabel(
  chunk: TranscriptChunkMessage,
  meDisplayName: string,
  counterpartyDisplayName: string,
): string {
  if (chunk.speaker === "me") return meDisplayName;
  if (chunk.speaker === "counterparty") return counterpartyDisplayName;
  return chunk.speaker;
}

function _formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export function TranscriptPane({
  chunks,
  meDisplayName,
  counterpartyDisplayName,
  meetingId,
  rerunPending = false,
}: TranscriptPaneProps) {
  const { t } = useTranslation();

  // Slice-11 polling: enabled whenever the meeting row reports
  // `rerun_asr_pending` OR the last poll said the task is still pending.
  // The query is `enabled: false` when there's no meetingId (legacy
  // pre-slice-11 caller) so we don't fire spurious requests.
  const statusQuery = useQuery(
    rerunStatusQueryOptions(meetingId ?? "", {
      enabled: Boolean(meetingId) && rerunPending,
      refetchInterval: (q) => (isRerunPending(q.state.data) ? 1000 : false),
    }),
  );
  // Invalidate transcript cache + meeting row on pending → idle transition.
  useTranscriptInvalidationOnRerunComplete(meetingId ?? "", statusQuery.data?.status);

  const overlayVisible = Boolean(meetingId) && (rerunPending || isRerunPending(statusQuery.data));
  const processed = statusQuery.data?.chunks_processed ?? 0;
  const total = statusQuery.data?.chunks_total ?? 0;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>{t("meetings.session.transcriptHeading")}</CardTitle>
      </CardHeader>
      <CardContent className="relative flex flex-1 flex-col overflow-hidden">
        {overlayVisible ? (
          <div
            data-testid="transcript-rerun-overlay"
            className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 bg-(--color-card)/90 text-sm text-(--color-muted-foreground)"
          >
            <p>{t("meetings.session.rerunOverlay")}</p>
            <p className="text-xs">
              {total > 0
                ? t("meetings.session.rerunOverlayProgress", { processed, total })
                : t("meetings.session.rerunOverlayEstimating")}
            </p>
          </div>
        ) : null}
        {chunks.length === 0 ? (
          <div
            data-testid="transcript-empty"
            className="py-8 text-center text-sm text-(--color-muted-foreground)"
          >
            {t("meetings.session.transcriptEmpty")}
          </div>
        ) : (
          <ol className="flex-1 space-y-3 overflow-y-auto pr-1">
            {chunks.map((chunk, idx) => (
              <li
                key={`${chunk.started_at}-${idx}`}
                data-testid="transcript-chunk"
                data-speaker={chunk.speaker}
                className={cn(
                  // Slice-7 visual: each chunk gets a 4px left accent
                  // border (counterparty primary, me secondary/muted) and
                  // body text in default text-foreground (NOT colored).
                  "rounded-md border-l-4 bg-(--color-card) p-3 text-sm",
                  chunk.speaker === "counterparty"
                    ? "border-l-(--color-primary)"
                    : "border-l-(--color-muted-foreground)",
                )}
              >
                <div className="mb-1 flex items-center gap-2 text-xs text-(--color-muted-foreground)">
                  <span className="font-medium">
                    {_speakerLabel(chunk, meDisplayName, counterpartyDisplayName)}
                  </span>
                  <span aria-hidden>·</span>
                  <span>{_formatTime(chunk.started_at)}</span>
                </div>
                <p className="break-words whitespace-pre-wrap text-(--color-foreground)">
                  {chunk.text}
                </p>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
