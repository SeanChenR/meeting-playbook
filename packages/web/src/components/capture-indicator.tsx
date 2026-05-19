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

import { useEffect, useRef, useState } from "react";
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
  const out: Record<Stream, number | null> = { me: null, counterparty: null };
  for (const c of chunks) {
    if (c.speaker !== "me" && c.speaker !== "counterparty") continue;
    const ts = new Date(c.started_at).getTime();
    if (!Number.isFinite(ts)) continue;
    const prev = out[c.speaker];
    if (prev === null || ts > prev) out[c.speaker] = ts;
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
  const startedRef = useRef<Record<Stream, number | null>>({ me: null, counterparty: null });

  // Track first time each stream becomes active. Component-managed so the
  // calling site stays unchanged from slice-7 era.
  useEffect(() => {
    if (streamStatus === null) {
      startedRef.current = { me: null, counterparty: null };
      return;
    }
    const now = Date.now();
    const next = { ...startedRef.current };
    let changed = false;
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
    if (changed) startedRef.current = next;
  }, [streamStatus]);

  // Trigger a re-render after 8s so a stream that has been active without
  // any chunks flips from `connecting` to `listening`.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (streamStatus === null) return;
    const anyActive = Object.values(streamStatus).some((s) => s === "active");
    if (!anyActive) return;
    const id = window.setTimeout(() => setTick((n) => n + 1), CONNECTING_WINDOW_MS);
    return () => window.clearTimeout(id);
  }, [streamStatus]);

  if (streamStatus === null) return null;

  const now = nowMs ?? Date.now();
  const derivedLastChunkAt =
    lastChunkAt === undefined ? _deriveLastChunkAtFromChunks(chunks) : null;

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
    return startedRef.current[stream];
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
