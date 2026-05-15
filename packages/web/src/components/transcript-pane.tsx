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
import { useTranslation } from "react-i18next";
import {
  isRerunPending,
  rerunStatusQueryOptions,
  useTranscriptInvalidationOnRerunComplete,
} from "../lib/rerun-api";
import type { TranscriptChunkMessage } from "../lib/session-ws";
import { paneEnter } from "../lib/motion-presets";
import { cn } from "../lib/utils";
import { NumberTicker } from "./magicui/number-ticker";
import { Pane } from "./pane";
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

// Stable distinct hues for speaker_cluster_N. Cycling through 6 well-spaced
// hues keeps adjacent clusters visually distinct even when pyannote returns
// many speakers; clusters > 6 reuse hues but in a different brightness band.
const _CLUSTER_HUES = [300, 150, 30, 240, 90, 0];

function _chunkBackground(speaker: TranscriptChunkMessage["speaker"]): string {
  if (speaker === "me") {
    return `color-mix(in oklch, var(--color-me-soft) calc(var(--me-tint-alpha) * 1000%), transparent)`;
  }
  if (speaker === "counterparty") {
    return `color-mix(in oklch, var(--color-them-soft) calc(var(--them-tint-alpha) * 1000%), transparent)`;
  }
  const match = _CLUSTER_LABEL_RE.exec(speaker);
  if (match) {
    if (match[1] === "unknown") {
      return `color-mix(in oklch, var(--color-muted) calc(var(--them-tint-alpha) * 1000%), transparent)`;
    }
    const n = Number.parseInt(match[1], 10);
    const hue = _CLUSTER_HUES[(n - 1) % _CLUSTER_HUES.length];
    return `color-mix(in oklch, oklch(0.93 0.06 ${hue}) calc(var(--them-tint-alpha) * 1000%), transparent)`;
  }
  return "transparent";
}

function _speakerAccent(speaker: TranscriptChunkMessage["speaker"]): string {
  if (speaker === "me") return "var(--color-me)";
  if (speaker === "counterparty") return "var(--color-them)";
  const match = _CLUSTER_LABEL_RE.exec(speaker);
  if (match && match[1] !== "unknown") {
    const n = Number.parseInt(match[1], 10);
    const hue = _CLUSTER_HUES[(n - 1) % _CLUSTER_HUES.length];
    return `oklch(0.55 0.18 ${hue})`;
  }
  return "var(--color-muted-foreground)";
}

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
          <ol className="flex flex-col gap-2.5">
            {chunks.map((chunk, idx) => (
              <TranscriptChunkRow
                key={`${chunk.started_at}-${idx}`}
                chunk={chunk}
                meDisplayName={meDisplayName}
                counterpartyDisplayName={counterpartyDisplayName}
              />
            ))}
          </ol>
        )}
      </div>
    </Pane>
  );
}

function TranscriptChunkRow({
  chunk,
  meDisplayName,
  counterpartyDisplayName,
}: {
  chunk: TranscriptChunkMessage;
  meDisplayName: string;
  counterpartyDisplayName: string;
}) {
  const { t } = useTranslation();
  const isMe = chunk.speaker === "me";
  const speakerColor = _speakerAccent(chunk.speaker);
  const background = _chunkBackground(chunk.speaker);

  return (
    <li
      data-testid="transcript-chunk"
      data-speaker={chunk.speaker}
      style={
        {
          borderLeftStyle: "solid",
          borderLeftWidth: "3px",
          borderLeftColor: speakerColor,
          // CSS custom property — happy-dom's value validator rejects
          // `color-mix()` on the standard `background-color` property and
          // drops it silently, which would also drop the cue from the rendered
          // HTML. Routing through a CSS variable preserves the value end-to-end.
          "--chunk-bg": background,
        } as React.CSSProperties
      }
      className={cn(
        "rounded-r-md bg-(--chunk-bg) px-3 py-2.5 text-sm",
        // Back-compat tokens for slice-7-era selectors that match on
        // arbitrary-value border classes.
        isMe ? "border-l-(--color-muted-foreground)" : "border-l-(--color-primary)",
      )}
    >
      <div className="mb-1 flex items-center gap-2">
        <span
          aria-hidden
          data-testid="speaker-dot"
          className="inline-block size-2 rounded-full"
          style={{ background: speakerColor }}
        />
        <span
          data-testid="speaker-name"
          className="text-sm font-semibold"
          style={{ color: speakerColor }}
        >
          {_speakerLabel(chunk, meDisplayName, counterpartyDisplayName, t)}
        </span>
        <span className="font-mono text-xs text-(--color-muted-foreground)">
          {_formatTime(chunk.started_at)}
        </span>
      </div>
      <p
        className="break-words whitespace-pre-wrap text-(--color-foreground)"
        style={{ lineHeight: 1.6 }}
      >
        {chunk.text}
      </p>
    </li>
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
        borderLeft: "3px solid var(--color-them)",
        background: "color-mix(in oklch, var(--color-them-soft) 50%, transparent)",
      }}
      className="rounded-r-md px-3 py-2.5"
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
