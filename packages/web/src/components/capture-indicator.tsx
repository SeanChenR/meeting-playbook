/**
 * CaptureIndicator — ui-overhaul-animated-surfaces task 3.2 + 3.3.
 *
 * Three-state bar visualizer per stream (replacing the random-amplitude
 * sparkline). Each row emits exactly one of four discrete `data-state`
 * values:
 *
 *   - `connecting` — capture is active but no transcript_chunk has
 *     arrived within the first 8 seconds since the stream became active.
 *     Tone = `warning` (orange), slow pulse.
 *   - `speaking`   — capture is active AND a transcript_chunk arrived
 *     within the last ~2 seconds. Tone = `me` / `them` per stream.
 *   - `listening`  — capture is active but stale (no recent chunk)
 *     OR backend reports `silence`. Tone = `me` / `them` per stream.
 *   - `off`        — backend reports `stopped` OR `ending=true`.
 *     Muted baseline.
 *
 * Backend message contract unchanged (per design.md): we layer the
 * heuristic on top of existing `streamStatus` + the `chunks` array
 * already exposed to the detail page. Callers MAY override
 * `streamStartedAt` / `lastChunkAt` / `nowMs` for deterministic tests.
 *
 * Visible label per row resolves from
 * `meetings.session.barVisualizer.<state>` (omitted when `off`).
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Stream, TranscriptChunkMessage } from "../lib/session-ws";
import { BarVisualizer, type BarVisualizerTone } from "./ui/bar-visualizer";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

export type StreamPillState = "active" | "silence" | "stopped";
export type CaptureIndicatorState = "connecting" | "listening" | "speaking" | "off";

export interface CaptureIndicatorProps {
  streamStatus: Record<Stream, StreamPillState> | null;
  meDisplayName: string;
  counterpartyDisplayName: string;
  ending?: boolean;
  /** Optional: live transcript chunks. Used to derive `lastChunkAt` when
   * the caller does not pass one explicitly. */
  chunks?: ReadonlyArray<TranscriptChunkMessage>;
  /** Per-stream timestamp (ms) of the most recent transcript_chunk. Test-
   * injectable; defaults to derivation from `chunks`. */
  lastChunkAt?: Partial<Record<Stream, number | null>>;
  /** Per-stream timestamp (ms) when the stream first became active. Test-
   * injectable; defaults to internal tracking. */
  streamStartedAt?: Partial<Record<Stream, number | null>>;
  /** Override `Date.now()` for deterministic tests. */
  nowMs?: number;
}

const STREAM_ORDER: Stream[] = ["me", "counterparty"];
const CONNECTING_WINDOW_MS = 8_000;
const SPEAKING_WINDOW_MS = 2_000;

function _toneFor(stream: Stream): BarVisualizerTone {
  return stream === "me" ? "me" : "them";
}

function _deriveLastChunkAtFromChunks(
  chunks: ReadonlyArray<TranscriptChunkMessage>,
): Record<Stream, number | null> {
  // Chunks are chronological; iterate backwards and bail out once both
  // speakers have a latest timestamp. Reduces avg complexity from O(N) to
  // O(1) on long meetings — gemini PR #50 MEDIUM (capture-indicator.tsx:74).
  const out: Record<Stream, number | null> = { me: null, counterparty: null };
  for (let i = chunks.length - 1; i >= 0; i -= 1) {
    const c = chunks[i];
    if (!c) continue;
    if (out.me !== null && out.counterparty !== null) break;
    if (c.speaker !== "me" && c.speaker !== "counterparty") continue;
    if (out[c.speaker] !== null) continue;
    const ts = new Date(c.started_at).getTime();
    if (Number.isFinite(ts)) out[c.speaker] = ts;
  }
  return out;
}

function _deriveState(args: {
  stream: Stream;
  status: StreamPillState;
  ending: boolean;
  streamStartedAt: number | null;
  lastChunkAt: number | null;
  now: number;
}): CaptureIndicatorState {
  const { status, ending, streamStartedAt, lastChunkAt, now } = args;
  if (ending) return "off";
  if (status === "stopped") return "off";
  if (status === "silence") return "listening";
  // status === "active"
  if (lastChunkAt !== null && now - lastChunkAt <= SPEAKING_WINDOW_MS) return "speaking";
  if (
    lastChunkAt === null &&
    streamStartedAt !== null &&
    now - streamStartedAt < CONNECTING_WINDOW_MS
  ) {
    return "connecting";
  }
  return "listening";
}

export function CaptureIndicator({
  streamStatus,
  meDisplayName: _me,
  counterpartyDisplayName: _cp,
  ending = false,
  chunks = [],
  lastChunkAt,
  streamStartedAt,
  nowMs,
}: CaptureIndicatorProps) {
  const { t } = useTranslation();
  // Track first time each stream becomes active. Stored as state so the
  // first render after a stream activates already sees the timestamp — a
  // ref would lag one render and emit `listening` before `connecting`.
  // Gemini PR #50 MEDIUM (capture-indicator.tsx:145 #1).
  const [startedAt, setStartedAt] = useState<Record<Stream, number | null>>({
    me: null,
    counterparty: null,
  });

  useEffect(() => {
    if (streamStatus === null) {
      setStartedAt({ me: null, counterparty: null });
      return;
    }
    setStartedAt((prev) => {
      const now = Date.now();
      let changed = false;
      const next = { ...prev };
      for (const s of STREAM_ORDER) {
        if (streamStatus[s] === "active" && next[s] === null) {
          next[s] = now;
          changed = true;
        }
        if (streamStatus[s] === "stopped" && next[s] !== null) {
          next[s] = null;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [streamStatus]);

  // Stable 1s tick while any stream is active so `connecting → listening`
  // transitions at the right time. A `setTimeout` reset on every
  // `streamStatus` update would push the deadline forward indefinitely
  // under chunk-heavy WS traffic — gemini PR #50 MEDIUM (line 145 #2).
  const [, setTick] = useState(0);
  const anyActive =
    streamStatus !== null && Object.values(streamStatus).some((s) => s === "active");
  useEffect(() => {
    if (!anyActive) return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [anyActive]);

  // Memoize the chunks-derived map so big transcripts don't recompute on
  // every render — gemini PR #50 MEDIUM (capture-indicator.tsx:151).
  const derivedLastChunkAt = useMemo(
    () => (lastChunkAt === undefined ? _deriveLastChunkAtFromChunks(chunks) : null),
    [lastChunkAt, chunks],
  );

  if (streamStatus === null) return null;

  const now = nowMs ?? Date.now();

  function _resolveLastChunkAt(stream: Stream): number | null {
    if (lastChunkAt !== undefined) {
      return lastChunkAt[stream] ?? null;
    }
    return derivedLastChunkAt?.[stream] ?? null;
  }

  function _resolveStartedAt(stream: Stream): number | null {
    if (streamStartedAt !== undefined) {
      return streamStartedAt[stream] ?? null;
    }
    return startedAt[stream];
  }

  return (
    <div
      data-testid="capture-indicator-group"
      className="flex flex-col gap-2 rounded-md border border-(--color-border) bg-(--color-muted)/40 p-2.5"
    >
      {STREAM_ORDER.map((stream) => {
        const status = streamStatus[stream];
        const state = _deriveState({
          stream,
          status,
          ending,
          streamStartedAt: _resolveStartedAt(stream),
          lastChunkAt: _resolveLastChunkAt(stream),
          now,
        });
        const tone: BarVisualizerTone = state === "connecting" ? "warning" : _toneFor(stream);
        const label = state === "off" ? "" : t(`meetings.session.barVisualizer.${state}` as const);
        const visualizerAriaLabel = label || t("meetings.session.captureLabelMe", { name: stream });

        return (
          <Tooltip key={stream}>
            <TooltipTrigger asChild>
              <div
                data-testid="capture-indicator"
                data-stream={stream}
                data-state={state}
                className="flex items-center gap-2"
              >
                <BarVisualizer state={state} tone={tone} ariaLabel={visualizerAriaLabel} />
                {label ? (
                  <span
                    data-testid="capture-indicator-label"
                    className="text-xs text-(--color-foreground)"
                  >
                    {label}
                  </span>
                ) : null}
              </div>
            </TooltipTrigger>
            <TooltipContent>{t("ui.tooltip.capture")}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
