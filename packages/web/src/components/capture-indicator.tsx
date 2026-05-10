/**
 * CaptureIndicator — per-stream status pills for an active capture session.
 *
 * Slice-07: renders ONE pill per stream (me + counterparty) side-by-side,
 * each driven by its own `StreamStatus`. Color tokens echo the TranscriptPane
 * accent so the two pills visually map to chunks below.
 *
 * State variants per pill:
 *   - active           → accent color + pulsing dot + "{display_name} 擷取中"
 *   - silence          → destructive color + static dot + "{display_name} 30s 無聲"
 *   - stopped          → muted color + static dot + "{display_name} 已停止"
 *
 * The `ending` global phase greys ALL pills (server is draining; mute the
 * detail). NO emojis (per UI feedback memory).
 */

import { useTranslation } from "react-i18next";
import type { Stream } from "../lib/session-ws";
import { cn } from "../lib/utils";

export type StreamPillState = "active" | "silence" | "stopped";

export interface CaptureIndicatorProps {
  // Slice-7: per-stream state mapping. `null` = the session is not in
  // progress (idle / ended) and the indicator is hidden.
  streamStatus: Record<Stream, StreamPillState> | null;
  meDisplayName: string;
  counterpartyDisplayName: string;
  // Global "ending" override: overrides all pills to a muted "處理最後音訊…" look.
  ending?: boolean;
}

const STREAM_ORDER: Stream[] = ["me", "counterparty"];

export function CaptureIndicator({
  streamStatus,
  meDisplayName,
  counterpartyDisplayName,
  ending = false,
}: CaptureIndicatorProps) {
  const { t } = useTranslation();
  if (streamStatus === null) return null;

  function _displayName(stream: Stream): string {
    return stream === "me" ? meDisplayName : counterpartyDisplayName;
  }

  function _label(stream: Stream, status: StreamPillState): string {
    if (ending) return t("meetings.session.endingHint");
    if (status === "stopped")
      return t("meetings.session.streamStopped", { name: _displayName(stream) });
    if (status === "silence") {
      const key =
        stream === "counterparty"
          ? "meetings.session.silenceWarningCounterparty"
          : "meetings.session.silenceWarningMe";
      return t(key, { name: _displayName(stream) });
    }
    return t("meetings.session.capturingNamed", { name: _displayName(stream) });
  }

  return (
    <div className="inline-flex flex-wrap items-center gap-2" data-testid="capture-indicator-group">
      {STREAM_ORDER.map((stream) => {
        const status: StreamPillState = streamStatus[stream];
        const isWarning = !ending && status === "silence";
        const isStopped = ending || status === "stopped";

        // Color resolution:
        //  - ending → muted (overrides everything)
        //  - silence → destructive
        //  - stopped → muted
        //  - active counterparty → primary
        //  - active me → secondary / muted-foreground (matches TranscriptPane accent)
        const containerCls = cn(
          "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium",
          isWarning
            ? "bg-(--color-destructive)/10 text-(--color-destructive)"
            : isStopped
              ? "bg-(--color-muted) text-(--color-muted-foreground)"
              : stream === "counterparty"
                ? "bg-(--color-primary)/10 text-(--color-primary)"
                : "bg-(--color-secondary) text-(--color-secondary-foreground)",
        );

        const dotCls = cn(
          "inline-block h-2 w-2 rounded-full",
          isWarning
            ? "bg-(--color-destructive)"
            : isStopped
              ? "bg-(--color-muted-foreground)"
              : stream === "counterparty"
                ? "bg-(--color-primary) animate-pulse"
                : "bg-(--color-muted-foreground) animate-pulse",
        );

        return (
          <div
            key={stream}
            data-testid="capture-indicator"
            data-stream={stream}
            data-state={ending ? "ending" : status}
            className={containerCls}
          >
            <span aria-hidden className={dotCls} />
            {_label(stream, status)}
          </div>
        );
      })}
    </div>
  );
}
