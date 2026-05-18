/**
 * CaptureIndicator — slice ui-overhaul-claude-design task 5.3.
 *
 * Re-skinned to match the design bundle's bar-sparkline pattern:
 *   - One row per stream (麥克風/我方 + 系統音訊/對方)
 *   - Each row: pulsing dot + label (min-width 100px) + 10-bar sparkline
 *   - Bar heights animate to a per-tick amplitude when active; collapse
 *     to 1px when the stream is muted/stopped/ending.
 *   - Container is a 10px-padded, bordered surface-2 box that can sit
 *     side-by-side with the ASR Select inside MetadataCard.
 *
 * Drives 10 random amplitude bars per row at 200ms cadence so the user
 * sees motion even before we feed real audio frames. Tests assert the
 * structural contract (row count, bar count, recording=false dot state)
 * — they do NOT rely on the random amplitudes.
 *
 * Behavioural contract preserved from slice-7:
 *   - `streamStatus === null` → renders nothing (idle / not in_progress)
 *   - `ending=true` mutes both rows regardless of stream status
 *   - `data-testid="capture-indicator"` per row, with `data-stream` +
 *     `data-state` attributes for state-aware assertions.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Stream } from "../lib/session-ws";
import { cn } from "../lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

export type StreamPillState = "active" | "silence" | "stopped";

export interface CaptureIndicatorProps {
  streamStatus: Record<Stream, StreamPillState> | null;
  meDisplayName: string;
  counterpartyDisplayName: string;
  ending?: boolean;
}

const STREAM_ORDER: Stream[] = ["me", "counterparty"];
const BAR_COUNT = 10;

function _randomBars(): number[] {
  // Bars in [2..6]; matches the design bundle's amplitude range.
  return Array.from({ length: BAR_COUNT }, () => 2 + Math.floor(Math.random() * 5));
}

const _INITIAL_BARS = Array.from({ length: BAR_COUNT }, (_, i) => 2 + ((i * 3) % 5));

export function CaptureIndicator({
  streamStatus,
  meDisplayName,
  counterpartyDisplayName,
  ending = false,
}: CaptureIndicatorProps) {
  const { t } = useTranslation();
  const [bars, setBars] = useState<{ me: number[]; counterparty: number[] }>({
    me: _INITIAL_BARS,
    counterparty: _INITIAL_BARS,
  });

  // Tick bar amplitudes while at least one stream is active. Skip the
  // interval entirely when nothing is moving so happy-dom + reduced-motion
  // users don't pay for it.
  const anyActive =
    !ending && streamStatus !== null && Object.values(streamStatus).some((s) => s === "active");

  useEffect(() => {
    if (!anyActive) return;
    const id = window.setInterval(() => {
      setBars({ me: _randomBars(), counterparty: _randomBars() });
    }, 220);
    return () => window.clearInterval(id);
  }, [anyActive]);

  if (streamStatus === null) return null;

  function _label(stream: Stream): string {
    if (stream === "me") {
      return t("meetings.session.captureLabelMe", { name: meDisplayName });
    }
    return t("meetings.session.captureLabelCounterparty", { name: counterpartyDisplayName });
  }

  return (
    <div
      data-testid="capture-indicator-group"
      className="flex flex-col gap-2 rounded-md border border-(--color-border) bg-(--color-muted)/40 p-2.5"
    >
      {STREAM_ORDER.map((stream) => {
        const status = streamStatus[stream];
        const isActive = !ending && status === "active";
        const isMuted = ending || status === "stopped";
        const isWarning = !ending && status === "silence";
        const state = ending ? "ending" : status;
        const rowBars = bars[stream];

        return (
          <Tooltip key={stream}>
            <TooltipTrigger asChild>
              <div
                data-testid="capture-indicator"
                data-stream={stream}
                data-state={state}
                className="flex items-center gap-2"
              >
                <span
                  aria-hidden
                  className={cn(
                    "inline-block size-2 rounded-full",
                    isActive
                      ? "bg-(--color-destructive) animate-pulse"
                      : isWarning
                        ? "bg-(--color-destructive)"
                        : "bg-(--color-muted-foreground)",
                  )}
                />
                <span className="min-w-[100px] text-xs text-(--color-foreground)">
                  {_label(stream)}
                </span>
                <div className="flex h-3 flex-1 items-end gap-0.5">
                  {rowBars.map((b, i) => (
                    <span
                      key={i}
                      aria-hidden
                      data-testid="capture-indicator-bar"
                      className={cn(
                        "w-0.5 rounded-[1px] transition-[height,opacity] duration-200",
                        isActive
                          ? "bg-(--color-destructive)"
                          : isMuted
                            ? "bg-(--color-border)"
                            : "bg-(--color-destructive)/60",
                      )}
                      style={{
                        height: isActive ? `${b * 1.6}px` : "1px",
                        opacity: isActive ? 0.55 + b / 12 : 1,
                      }}
                    />
                  ))}
                </div>
              </div>
            </TooltipTrigger>
            <TooltipContent>{t("ui.tooltip.capture")}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
