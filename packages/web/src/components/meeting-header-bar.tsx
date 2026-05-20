/**
 * MeetingHeaderBar — single-row title strip.
 *
 * v4 layout (claude-design follow-up round 4): everything informational about
 * the meeting collapses onto one wrapping row:
 *
 *   [title] [status pill] [time] [recording-dot]
 *   [對方 avatar(s) name] [我方 avatar name]
 *   [tag chips...] [+ add tag]
 *   [capture indicator — only when in_progress / ending]
 *
 * The action buttons + counts + mode/asr cards live in <MeetingDetailActionBar>
 * below this strip; the ⋯ overflow menu has been retired (per Sean: every
 * affordance is now visible in either the action bar or the header strip).
 */

import { Plus, Tags } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { MeetingDetail } from "../lib/meetings-api";
import {
  resolveMeetingBucket,
  type MeetingDateBucket as MeetingBucket,
} from "../lib/meetings-bucket";
import { recordingStatusVisual, resolveRecordingStatus } from "../lib/meetings-recording-status";
import { TAG_PALETTE } from "../lib/tag-palette";
import { AvatarGroup, parseCounterpartyNames } from "./animate-ui/avatar-group";
import { ShineBorder } from "./magicui/shine-border";
import { TagChip } from "./tags/tag-chip";
import { Avatar } from "./ui/avatar";

export type MeetingPhase = "idle" | "connecting" | "in_progress" | "ending" | "ended" | "error";

export interface MeetingHeaderBarProps {
  meeting: MeetingDetail;
  phase: MeetingPhase;
  /** Capture indicator (live stream status). Hidden outside in_progress/ending. */
  captureIndicator?: ReactNode;
  /** Optional callback when the user clicks the tag "+" affordance. */
  onTagsOpen?: () => void;
}

function _bucketDotColor(bucket: MeetingBucket): string {
  if (bucket === "needs_recording") return "var(--color-warning)";
  if (bucket === "upcoming") return "var(--color-info)";
  return "var(--color-muted-foreground)";
}

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

interface TagLike {
  id: string;
  name: string;
  color?: string | null;
}

// Fallback for tags missing a `color` field — picks the first entry of the
// canonical TAG_PALETTE so the chip stays inside the design-token allowlist
// (raw-hex scan rejects per-file literals).
const _FALLBACK_TAG_COLOR: string = TAG_PALETTE[0] as string;

export function MeetingHeaderBar({
  meeting,
  phase,
  captureIndicator,
  onTagsOpen,
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
  const tags: TagLike[] = (meeting.tags ?? []) as TagLike[];

  return (
    <div
      data-testid="meeting-header-bar"
      className="relative overflow-hidden rounded-2xl bg-(--color-surface) shadow-(--shadow-sm) ring-1 ring-(--color-border)/60"
    >
      <ShineBorder duration={16} />
      <div className="relative z-[1] flex flex-wrap items-center gap-x-4 gap-y-2.5 px-5 py-4">
        <h1
          data-testid="meeting-title"
          className="text-[22px] font-semibold leading-tight tracking-tight text-(--color-foreground)"
        >
          {meeting.title}
        </h1>

        <_StatusPill bucket={bucket} label={t(`meetings.detail.bucketLabel.${bucket}`)} />

        {scheduledWindow && (
          <>
            <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />
            <span className="text-[13px] tabular-nums text-(--color-muted-foreground)">
              {scheduledWindow}
            </span>
          </>
        )}

        <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />

        {/* 對方 */}
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
              <span className="text-[13px] font-medium">{meeting.counterparty_display_name}</span>
            </>
          ) : (
            <>
              <AvatarGroup names={counterpartyNames} max={3} />
              <span className="text-[13px] font-medium">
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

        {/* Tags block — Sean asked for a divider + Tags icon to mark this as
          its own conceptual section. */}
        {(tags.length > 0 || onTagsOpen) && (
          <>
            <span aria-hidden className="h-3.5 w-px bg-(--color-border)" />
            <div className="flex flex-wrap items-center gap-1.5" data-testid="header-tags-inline">
              <Tags
                className="size-3.5 text-(--color-muted-foreground)"
                strokeWidth={1.5}
                aria-hidden
              />
              {tags.map((tag) => (
                <TagChip key={tag.id} name={tag.name} color={tag.color ?? _FALLBACK_TAG_COLOR} />
              ))}
              {onTagsOpen && (
                <button
                  type="button"
                  onClick={onTagsOpen}
                  data-testid="header-tags-add"
                  aria-label={t("meetings.detail.tagsAdd")}
                  className="inline-flex size-5 items-center justify-center rounded-full border border-dashed border-(--color-border) text-(--color-muted-foreground) transition-colors hover:border-(--color-primary) hover:text-(--color-primary)"
                >
                  <Plus className="size-3" strokeWidth={1.8} aria-hidden />
                </button>
              )}
            </div>
          </>
        )}

        {/* Right-edge cluster — capture indicator (only when live) + the
            recording-status pill. ml-auto pushes whichever is shown out
            to the right so the header doesn't end with empty whitespace. */}
        {(captureIndicator && (phase === "in_progress" || phase === "ending")) ||
        recordingStatus !== "hidden" ? (
          <div className="ml-auto flex items-center gap-3">
            {captureIndicator && (phase === "in_progress" || phase === "ending") && (
              <div data-testid="header-capture-indicator">{captureIndicator}</div>
            )}
            {recordingStatus !== "hidden" && (
              <span
                data-testid="header-recording-status"
                className="inline-flex items-center gap-1.5 rounded-full bg-(--color-surface-2) py-[3px] pl-[7px] pr-[10px] text-[11.5px] font-medium tracking-wide text-(--color-foreground)"
              >
                <span
                  aria-hidden
                  data-testid="header-recording-dot"
                  className="size-[7px] rounded-full"
                  style={{
                    background: `var(${recordingVisual.colorVar})`,
                    boxShadow: `0 0 0 3px color-mix(in oklch, var(${recordingVisual.colorVar}) 25%, transparent)`,
                  }}
                />
                {t(recordingVisual.i18nKey)}
              </span>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
