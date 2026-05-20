/**
 * TranscriptPane — slice ui-overhaul-claude-design task 6.1.
 *
 * Re-skinned with the shared `Pane` shell (accent = `--color-them` per
 * design bundle). Each chunk now renders four speaker-contrast cues
 * simultaneously:
 *
 *   1. `border-left: 3px` colored by `--color-me` / `--color-them`
 *   2. background filled via `color-mix(in oklch, var(--color-{me|them}-soft)
 *      calc(var(--{me|them}-tint-alpha) * 1000%), transparent)`
 *   3. a `Dot` (data-testid="speaker-dot") tinted by the same speaker color
 *   4. speaker name rendered semibold (font-weight 600) in the speaker color
 *
 * Plus mono-font timestamp + 1.6 line-height body (per design bundle copy).
 *
 * `data-testid="transcript-chunk"` + `data-speaker` attributes preserved so
 * existing tests still resolve. The slice-7 `border-l-(--color-primary)`
 * class is kept on counterparty + `border-l-(--color-muted-foreground)`
 * on me as a back-compat marker for legacy assertions; they sit underneath
 * the design-bundle inline-style border-left so the visual stays correct.
 *
 * Live placeholder ("正在說話…") still mounts when receiving an in-flight
 * counterparty chunk via `LiveChunkPlaceholder` — Skeleton bars + pulsing dot.
 */

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  isRerunPending,
  rerunStatusQueryOptions,
  useTranscriptInvalidationOnRerunComplete,
} from "../lib/rerun-api";
import type { TranscriptChunkMessage } from "../lib/session-ws";
import { paneEnter } from "../lib/motion-presets";
import { _resolveClusterColor } from "../lib/transcript-color-schemes";
import { useClusterSpeakerLabels } from "../hooks/use-cluster-speaker-labels";
import { miniPlayerStore } from "../hooks/use-mini-player";
import { useTranscriptColorPref } from "../hooks/use-transcript-color-pref";
import { cn } from "../lib/utils";
import { AnimatedList, AnimatedListItem } from "./magicui/animated-list";
import { NumberTicker } from "./magicui/number-ticker";
import { Pane } from "./pane";
import { SpeakerColorPopover } from "./speaker-color-popover";
import { TranscriptChunkRow as ChunkBody } from "./transcript-chunk-row";
import { Skeleton } from "./ui/skeleton";

export type ContrastLevel = "subtle" | "strong";

interface TranscriptPaneProps {
  chunks: TranscriptChunkMessage[];
  meDisplayName: string;
  counterpartyDisplayName: string;
  meetingId?: string;
  rerunPending?: boolean;
  /** Drives `--{me|them}-tint-alpha` override; defaults to "strong". */
  contrastLevel?: ContrastLevel;
}

const _CLUSTER_LABEL_RE = /^speaker_cluster_(\d+|unknown)$/;

function _speakerLabel(
  chunk: TranscriptChunkMessage,
  meDisplayName: string,
  counterpartyDisplayName: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (chunk.speaker === "me") return meDisplayName;
  if (chunk.speaker === "counterparty") return counterpartyDisplayName;
  // Slice-12 (ADR-0029): single-channel mode emits
  // `speaker_cluster_<N>` / `speaker_cluster_unknown` labels.
  const match = _CLUSTER_LABEL_RE.exec(chunk.speaker);
  if (match) {
    const token = match[1];
    if (token === "unknown") return t("meetings.session.speaker.cluster_unknown");
    return t("meetings.session.speaker.cluster", { n: token });
  }
  return chunk.speaker;
}

function _formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

// Slice-16: cluster color resolution moved to lib/transcript-color-schemes.ts
// so the user can pick a palette (default / vivid / pastel / high-contrast /
// grayscale) and override individual cluster colors. The pure resolver
// returns both `accent` and `background`; the helpers below preserve the
// previous two-call shape for incremental refactoring.

export function TranscriptPane({
  chunks,
  meDisplayName,
  counterpartyDisplayName,
  meetingId,
  rerunPending = false,
  contrastLevel = "strong",
}: TranscriptPaneProps) {
  const { t } = useTranslation();

  const statusQuery = useQuery(
    rerunStatusQueryOptions(meetingId ?? "", {
      enabled: Boolean(meetingId) && rerunPending,
      refetchInterval: (q) => (isRerunPending(q.state.data) ? 1000 : false),
    }),
  );
  useTranscriptInvalidationOnRerunComplete(meetingId ?? "", statusQuery.data?.status);

  const overlayVisible = Boolean(meetingId) && (rerunPending || isRerunPending(statusQuery.data));
  const processed = statusQuery.data?.chunks_processed ?? 0;
  const total = statusQuery.data?.chunks_total ?? 0;

  // contrastLevel hook: caller can dial down the per-chunk tint by inlining
  // a CSS variable override on the body. "strong" = ship the spec defaults
  // (--me-tint-alpha 0.14 / --them-tint-alpha 0.20 in dark mode); "subtle"
  // halves them.
  const tintStyle: React.CSSProperties =
    contrastLevel === "subtle"
      ? ({ "--me-tint-alpha": "0.05", "--them-tint-alpha": "0.08" } as React.CSSProperties)
      : {};

  return (
    <Pane
      data-testid="transcript-pane"
      title={t("meetings.session.transcriptHeading")}
      accent="var(--color-them)"
      bodyClassName="px-3.5 py-3 relative"
    >
      <div data-testid="transcript-pane-body" style={tintStyle}>
        <AnimatePresence initial={false}>
          {overlayVisible && (
            <motion.div
              key="rerun-overlay"
              data-testid="transcript-rerun-overlay"
              variants={paneEnter}
              initial="initial"
              animate="animate"
              exit="exit"
              className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 bg-(--color-card)/90 text-sm text-(--color-muted-foreground)"
            >
              <p>{t("meetings.session.rerunOverlay")}</p>
              <p className="text-xs">
                {total > 0 ? (
                  <span>
                    (<NumberTicker value={processed} data-testid="rerun-processed-ticker" />/{total}{" "}
                    chunks)
                  </span>
                ) : (
                  t("meetings.session.rerunOverlayEstimating")
                )}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
        {chunks.length === 0 ? (
          <div
            data-testid="transcript-empty"
            className="py-8 text-center text-sm text-(--color-muted-foreground)"
          >
            {t("meetings.session.transcriptEmpty")}
          </div>
        ) : (
          <AnimatedList as="ol" className="flex flex-col gap-2.5">
            {chunks.map((chunk, idx) => (
              <TranscriptChunkRow
                key={`${chunk.started_at}-${idx}`}
                chunk={chunk}
                idx={idx}
                meDisplayName={meDisplayName}
                counterpartyDisplayName={counterpartyDisplayName}
                meetingId={meetingId}
              />
            ))}
          </AnimatedList>
        )}
      </div>
    </Pane>
  );
}

function TranscriptChunkRow({
  chunk,
  idx,
  meDisplayName,
  counterpartyDisplayName,
  meetingId,
}: {
  chunk: TranscriptChunkMessage;
  /** Position in the rendered chunk list. Combined with started_at + speaker
   *  to form the fallback chunk id when `chunk.id` is absent — must mirror
   *  the composite key built in `detail.tsx → miniPlayerStore.setContext`
   *  so the play menu's `seekToChunk(chunkId)` resolves the right row. */
  idx: number;
  meDisplayName: string;
  counterpartyDisplayName: string;
  meetingId?: string;
}) {
  const { t } = useTranslation();
  const isMe = chunk.speaker === "me";
  const { pref } = useTranscriptColorPref();
  const { accent: speakerColor, background } = _resolveClusterColor(chunk.speaker, pref);

  // Slice-16 task 10.5/10.8: cluster speakers expose a chunk action
  // menu (Play / Edit text / Edit color / Rename speaker) via the body.
  const clusterMatch = _CLUSTER_LABEL_RE.exec(chunk.speaker);
  const clusterN =
    clusterMatch && clusterMatch[1] !== "unknown"
      ? Number.parseInt(clusterMatch[1] as string, 10)
      : null;
  const speakerNameRef = useRef<HTMLSpanElement | null>(null);
  const [colorPopoverOpen, setColorPopoverOpen] = useState(false);

  // Slice-16 task 10.3: per-meeting cluster label override.
  const { labels, setLabel } = useClusterSpeakerLabels(meetingId ?? "");
  const overrideLabel = clusterN !== null && labels[clusterN] ? labels[clusterN] : null;
  const speakerLabel =
    overrideLabel ?? _speakerLabel(chunk, meDisplayName, counterpartyDisplayName, t);

  // Chunk-id key: prefer real chunk.id (REST replay carries the DB
  // `tc_xxx` id; WS live frames may also carry one). Fall back to the
  // SAME composite key that `detail.tsx → miniPlayerStore.setContext`
  // builds — `${started_at}-${speaker}-${idx}` — otherwise live frames
  // without DB ids end up with a different id here than in the store,
  // and clicking "play this chunk" silently no-ops because
  // `seekToChunk(chunkId)` can't find a match in chunks_sorted.
  const chunkId = chunk.id ?? `${chunk.started_at}-${chunk.speaker}-${idx}`;
  const hasDbId = typeof chunk.id === "string" && chunk.id.length > 0;

  // refactor-meeting-detail-three-column 9d: optional `flag_reason` on chunk
  // surfaces a destructive-tinted chip in the meta line and a is-flag class on
  // the row. Backend currently does not populate this field; the type is a
  // pure frontend augmentation so the visual contract is ready for a future
  // backend feature (feature-transcript-objection-flag).
  const flagReason = (chunk as TranscriptChunkMessage & { flag_reason?: string | null })
    .flag_reason;
  const hasFlag = typeof flagReason === "string" && flagReason.length > 0;

  return (
    <AnimatedListItem
      className={cn(
        // Claude Design v2 alignment: fully rounded chunks with a thin
        // accent strip on the left. Implemented as an `inset box-shadow`
        // so the colored band naturally follows the rounded corner curve
        // (a pseudo-element clipped by overflow-hidden leaves a visible
        // gap at the top / bottom of each corner). Shadow width sits on
        // a CSS var so hover can interpolate it without re-rendering.
        "group relative rounded-xl bg-(--chunk-bg) px-3.5 py-3 text-sm",
        "ring-1 ring-(--color-border)/40 transition-all duration-150",
        // Hover: lift slightly, deepen the speaker-tinted ring, and grow
        // the accent strip 3px → 4px so the active chunk reads as the
        // visual focus without changing surrounding text colors.
        "hover:-translate-y-px hover:shadow-(--shadow-sm)",
        "hover:ring-(--chunk-accent)/35",
        hasFlag && "is-flag ring-(--color-destructive)/30 bg-(--color-destructive)/4",
      )}
      style={
        {
          "--chunk-bg": background,
          "--chunk-accent": hasFlag ? "var(--color-destructive)" : speakerColor,
          boxShadow: `inset 3px 0 0 0 ${hasFlag ? "var(--color-destructive)" : speakerColor}`,
        } as React.CSSProperties
      }
      itemProps={{
        "data-testid": "transcript-chunk",
        "data-speaker": chunk.speaker,
        "data-flag": hasFlag ? "true" : undefined,
      }}
    >
      <div className="mb-1 flex items-center gap-2">
        {/*
          Speaker label as a chip pill (Claude Design v2). The leading dot
          tucks inside the chip so the existing `speaker-dot` testid stays
          discoverable while the visual collapses into a single colored
          token. Background + text both pick up `--chunk-accent` so the
          chip auto-themes per speaker (cluster, me, them, flagged).
        */}
        <span
          ref={speakerNameRef}
          data-testid="speaker-name"
          className={cn(
            "inline-flex items-center gap-1 rounded-full",
            "px-2 py-0.5 text-xs font-semibold",
          )}
          style={{
            background: `color-mix(in oklch, ${speakerColor} 14%, transparent)`,
            color: speakerColor,
          }}
        >
          <span
            aria-hidden
            data-testid="speaker-dot"
            className="inline-block size-1.5 rounded-full"
            style={{ background: speakerColor }}
          />
          {speakerLabel}
        </span>
        {clusterN !== null && (
          <SpeakerColorPopover
            clusterN={clusterN}
            open={colorPopoverOpen}
            onOpenChange={setColorPopoverOpen}
            anchorRef={speakerNameRef}
          />
        )}
        <span className="font-mono text-xs text-(--color-muted-foreground)">
          {_formatTime(chunk.started_at)}
        </span>
        {hasFlag && (
          <span
            data-testid="transcript-chunk-flag-chip"
            className="rounded-full bg-(--color-destructive)/12 px-2 py-0.5 text-xs font-medium text-(--color-destructive)"
          >
            {flagReason}
          </span>
        )}
      </div>
      <ChunkBody
        meetingId={meetingId ?? ""}
        chunkId={chunkId}
        text={chunk.text}
        clusterN={clusterN}
        onPlay={(id) => miniPlayerStore.seekToChunk(id)}
        onEditColor={() => setColorPopoverOpen(true)}
        onRenameCommit={(n, label) => setLabel(n, label)}
      />
    </AnimatedListItem>
  );
}

/**
 * LiveChunkPlaceholder — render this at the tail of the chunk list when a
 * counterparty stream is mid-utterance and no transcript_chunk has arrived
 * yet. Currently no callers wire this in (the live transcript path streams
 * partial chunks); keep the export so the design bundle's affordance is
 * available in a future polish round.
 */
export function LiveChunkPlaceholder({ name }: { name: string }) {
  return (
    <div
      data-testid="transcript-live-placeholder"
      style={{
        background: "color-mix(in oklch, var(--color-them-soft) 50%, transparent)",
        boxShadow: "inset 3px 0 0 0 var(--color-them)",
      }}
      className="relative rounded-xl px-3.5 py-3 ring-1 ring-(--color-border)/40"
    >
      <div className="mb-1.5 flex items-center gap-2">
        <span
          aria-hidden
          className="inline-block size-2 animate-pulse rounded-full"
          style={{ background: "var(--color-them)" }}
        />
        <span className="text-sm font-semibold" style={{ color: "var(--color-them)" }}>
          {name}
        </span>
        <span className="text-xs text-(--color-muted-foreground)">…</span>
      </div>
      <div className="flex gap-1.5">
        <Skeleton className="h-2.5 w-[140px]" />
        <Skeleton className="h-2.5 w-[80px]" />
        <Skeleton className="h-2.5 w-[60px]" />
      </div>
    </div>
  );
}
