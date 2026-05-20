/**
 * MeetingHeaderBar — replaces MetadataCard on meeting detail page.
 *
 * Compact two-row horizontal block (NOT a card). Row 1: title + status pill
 * + scheduled-time window + 對方 (single Avatar or AvatarGroup) + 我方 (Avatar)
 * + recording-status indicator (4 states via resolveRecordingStatus) + optional
 * capture indicator. Row 2: status-driven primary actions + overflow menu
 * trigger slot.
 *
 * All visual affordances use Lucide icons (no emoji glyphs).
 */

import { Download, Play, Square, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { MeetingDetail } from "../lib/meetings-api";
import {
  resolveMeetingBucket,
  type MeetingDateBucket as MeetingBucket,
} from "../lib/meetings-bucket";
import { recordingStatusVisual, resolveRecordingStatus } from "../lib/meetings-recording-status";
import { AvatarGroup, parseCounterpartyNames } from "./animate-ui/avatar-group";
import { Avatar } from "./ui/avatar";
import { Button } from "./ui/button";

export type MeetingPhase = "idle" | "connecting" | "in_progress" | "ending" | "ended" | "error";

export interface MeetingHeaderBarProps {
  meeting: MeetingDetail;
  phase: MeetingPhase;
  onStart: () => void;
  onEnd: () => void;
  startDisabled?: boolean;
  /** Capture indicator (live stream status). Hidden outside in_progress/ending. */
  captureIndicator?: ReactNode;
  /** ⋯ overflow menu trigger element (built by detail.tsx). */
  menuTrigger?: ReactNode;
  /** Upload-audio button slot (only rendered when bucket === "needs_recording"). */
  uploadSlot?: ReactNode;
  /** Export button slot (always rendered). */
  exportSlot?: ReactNode;
}

function _bucketDotColor(bucket: MeetingBucket): string {
  if (bucket === "needs_recording") return "var(--color-warning)";
  if (bucket === "upcoming") return "var(--color-info)";
  return "var(--color-muted-foreground)"; // completed — soft past-tense feel
}

/**
 * Status pill — surface-2 background with a small coloured dot. Matches the
 * Claude Design `.status-pill` spec: subtle bg, 11.5px text, dot indicates
 * bucket. NOT a coloured badge.
 */
function _StatusPill({ bucket, label }: { bucket: MeetingBucket; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-(--color-surface-2) py-[3px] pl-[7px] pr-[9px] text-[11.5px] font-medium tracking-wide text-(--color-foreground)">
      <span
        aria-hidden
        className="size-[7px] rounded-full"
        style={{ background: _bucketDotColor(bucket) }}
      />
      {label}
    </span>
  );
}

function _fmtScheduledWindow(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
  locale: string,
): string {
  if (!startIso) return "";
  const start = new Date(startIso).toLocaleString(locale, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (!endIso) return start;
  const end = new Date(endIso).toLocaleString(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${start} – ${end}`;
}

function _primaryActions(props: {
  bucket: MeetingBucket;
  phase: MeetingPhase;
  startDisabled: boolean;
  onStart: () => void;
  onEnd: () => void;
  uploadSlot?: ReactNode;
  exportSlot?: ReactNode;
  t: (k: string) => string;
}): ReactNode {
  const { bucket, phase, startDisabled, onStart, onEnd, uploadSlot, exportSlot, t } = props;

  if (phase === "in_progress" || phase === "ending") {
    return (
      <Button
        type="button"
        size="sm"
        variant="destructive"
        onClick={onEnd}
        data-testid="header-end-meeting"
      >
        <Square className="size-3.5" strokeWidth={1.5} />
        {t("meetings.session.end")}
      </Button>
    );
  }

  if (bucket === "upcoming" && phase === "idle") {
    return (
      <>
        <Button
          type="button"
          size="sm"
          onClick={onStart}
          disabled={startDisabled}
          data-testid="header-start-meeting"
        >
          <Play className="size-3.5" strokeWidth={1.5} />
          {t("meetings.session.start")}
        </Button>
        {exportSlot}
      </>
    );
  }

  if (bucket === "needs_recording") {
    return (
      <>
        {uploadSlot}
        {exportSlot}
      </>
    );
  }

  // bucket === "completed" or fallback
  return <>{exportSlot}</>;
}

export function MeetingHeaderBar({
  meeting,
  phase,
  onStart,
  onEnd,
  startDisabled = false,
  captureIndicator,
  menuTrigger,
  uploadSlot,
  exportSlot,
}: MeetingHeaderBarProps) {
  const { t, i18n } = useTranslation();
  const bucket = resolveMeetingBucket(meeting);
  const counterpartyNames = parseCounterpartyNames(meeting.counterparty_display_name);
  const recordingStatus = resolveRecordingStatus(meeting);
  const recordingVisual = recordingStatusVisual(recordingStatus);
  const scheduledWindow = _fmtScheduledWindow(
    meeting.scheduled_start_at,
    meeting.scheduled_end_at,
    i18n.language,
  );

  return (
    <div
      data-testid="meeting-header-bar"
      className="flex flex-col gap-3 border-b border-(--color-border) pb-3.5"
    >
      {/* Row 1 — title + meta with vertical separators between groups */}
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
        <h1
          data-testid="meeting-title"
          className="text-[22px] font-semibold leading-tight tracking-tight text-(--color-foreground)"
        >
          {meeting.title}
        </h1>

        <_StatusPill bucket={bucket} label={t(`meetings.detail.bucketLabel.${bucket}`)} />

        <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />

        {scheduledWindow && (
          <span className="text-[13px] tabular-nums text-(--color-muted-foreground)">
            {scheduledWindow}
          </span>
        )}

        <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />

        {/* 對方 — single avatar or avatar-group */}
        <div className="flex items-center gap-1.5" data-testid="header-counterparty">
          <span className="text-[11px] uppercase tracking-wider text-(--color-muted-foreground)">
            {t("meetings.detail.counterpartyLabel")}
          </span>
          {counterpartyNames.length <= 1 ? (
            <>
              <Avatar
                alt={meeting.counterparty_display_name}
                fallback={meeting.counterparty_display_name[0] ?? "?"}
                className="size-[22px] text-[10px]"
              />
              <span className="text-sm font-medium">{meeting.counterparty_display_name}</span>
            </>
          ) : (
            <>
              <AvatarGroup names={counterpartyNames} max={3} />
              <span className="text-sm font-medium">
                {t("meetings.detail.counterpartyGroupLabel", {
                  name: counterpartyNames[0],
                  count: counterpartyNames.length,
                })}
              </span>
            </>
          )}
        </div>

        {/* 我方 */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-(--color-muted-foreground)">
            {t("meetings.detail.meLabel")}
          </span>
          <Avatar
            alt={meeting.me_display_name}
            fallback={meeting.me_display_name[0] ?? "?"}
            className="size-[22px] text-[10px]"
          />
          <span className="text-[13px] font-medium">{meeting.me_display_name}</span>
        </div>

        {/* Recording status (hidden when bucket === "upcoming") */}
        {recordingStatus !== "hidden" && (
          <>
            <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />
            <div
              className="flex items-center gap-1.5 text-[12px] text-(--color-muted-foreground)"
              data-testid="header-recording-status"
            >
              <span
                aria-hidden
                data-testid="header-recording-dot"
                className="size-[7px] rounded-full ring-4 ring-(--color-success)/15"
                style={{
                  background: `var(${recordingVisual.colorVar})`,
                  // Mirror the ring tint colour to match the dot so non-success states don't get a green ring.
                  ["--tw-ring-color" as never]: `var(${recordingVisual.colorVar})`,
                }}
              />
              <span>{t(recordingVisual.i18nKey)}</span>
            </div>
          </>
        )}

        {captureIndicator && (phase === "in_progress" || phase === "ending") && (
          <div data-testid="header-capture-indicator">{captureIndicator}</div>
        )}
      </div>

      {/* Row 2 — actions + ⋯ menu */}
      <div className="flex items-center justify-end gap-2">
        {_primaryActions({
          bucket,
          phase,
          startDisabled,
          onStart,
          onEnd,
          uploadSlot,
          exportSlot,
          t,
        })}
        {menuTrigger}
      </div>
    </div>
  );
}

/**
 * Helper Lucide icons exported for use by detail.tsx when building the upload
 * / export slots passed into <MeetingHeaderBar>. Centralised here to keep the
 * icon vocabulary consistent.
 */
export const HeaderIcons = { Play, Square, Upload, Download };
