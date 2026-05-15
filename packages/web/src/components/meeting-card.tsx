/**
 * MeetingCard — slice meetings-ux-revamp.
 *
 * Extracted from `routes/meetings/list.tsx` so the new MeetingsKanban
 * can render the same shape per column. Visual contract is unchanged
 * from the slice ui-overhaul-claude-design version: 3px left status
 * bar, status badge with dot, title + counterparty/me row, bottom
 * calendar icon + duration. Hover lifts the card and tightens the
 * border via the primary tint.
 */

import { Link, useNavigate } from "@tanstack/react-router";
import { Calendar as CalendarIcon, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "./ui/badge";
import { TagChip } from "./tags/tag-chip";
import { TagPicker } from "./tags/tag-picker";
import type { Meeting, MeetingStatus } from "../lib/meetings-api";

const STATUS_COLOR: Record<MeetingStatus, string> = {
  scheduled: "var(--color-primary)",
  in_progress: "var(--color-destructive)",
  completed: "var(--color-muted-foreground)",
};

const STATUS_BADGE: Record<MeetingStatus, "default" | "success" | "outline"> = {
  scheduled: "outline",
  in_progress: "success",
  completed: "default",
};

function _durationMinutes(start: string, end: string | null): number | null {
  if (!end) return null;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return Math.round(ms / 60000);
}

function _formatTime(value: string, locale: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export interface MeetingCardProps {
  meeting: Meeting;
  /**
   * When true, render a hover-only "Upload audio" shortcut button
   * absolutely-positioned at the card's bottom-right corner. Click
   * navigates to /meetings/$id?action=upload so the detail page
   * auto-opens the upload dialog (slice-15 task 8.4).
   */
  showUploadShortcut?: boolean;
}

export function MeetingCard({ meeting, showUploadShortcut = false }: MeetingCardProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const color = STATUS_COLOR[meeting.status];
  const badgeVariant = STATUS_BADGE[meeting.status];
  const duration = _durationMinutes(meeting.scheduled_start_at, meeting.scheduled_end_at);
  const timeText = _formatTime(meeting.scheduled_start_at, i18n.language);

  const cardLink = (
    <Link
      {...({ to: `/meetings/${meeting.id}` } as { to: "/meetings/$id"; params: { id: string } })}
      data-testid="meeting-card"
      className="group relative block shrink-0 overflow-hidden rounded-lg border border-(--color-border) bg-(--color-card) p-5 shadow-sm transition-[box-shadow,border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-(--color-primary)/40 hover:shadow-md"
    >
      <span
        aria-hidden
        className="absolute left-0 top-0 h-full w-[3px]"
        style={{ background: color }}
      />
      <div className="flex items-center justify-between gap-2">
        <Badge variant={badgeVariant} className="gap-1.5">
          <span aria-hidden className="size-1.5 rounded-full" style={{ background: color }} />
          {t(`meetings.list.status.${meeting.status}`)}
        </Badge>
      </div>
      <h2
        data-testid="meeting-list-item-title"
        className="mt-3 text-lg font-semibold leading-snug tracking-tight text-(--color-foreground)"
      >
        {meeting.title}
      </h2>
      <p className="mt-2 text-sm text-(--color-muted-foreground)">
        <span className="font-medium text-(--color-foreground)">
          {meeting.counterparty_display_name}
        </span>{" "}
        · {meeting.me_display_name}
      </p>
      {(meeting.tags?.length ?? 0) > 0 && (
        <div data-testid="meeting-card-tags" className="mt-2 flex flex-wrap gap-1">
          {(meeting.tags ?? []).map((tag) => (
            <TagChip key={tag.id} name={tag.name} color={tag.color} />
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--color-muted-foreground)">
        <span className="inline-flex items-center gap-1">
          <CalendarIcon className="size-3" aria-hidden />
          {timeText}
        </span>
        {duration !== null && (
          <span>
            · {duration} {t("meetings.list.minutesShort")}
          </span>
        )}
      </div>
    </Link>
  );

  // Slice-17: every card carries a hover-only "+ tag" picker so the
  // user can attach / detach tags without entering the detail page.
  // Wrap the Link in a positioned group so the picker can sit absolutely
  // at the top-right without nesting inside <Link> (invalid HTML).
  return (
    <div className="group relative">
      {cardLink}
      <div
        data-testid="meeting-card-tag-shortcut"
        // Stop bubbling clicks reaching the underlying Link (TagPicker's
        // popover lives in the same DOM tree).
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        className="absolute right-3 top-3 z-10 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100"
      >
        <TagPicker
          meetingId={meeting.id}
          currentTags={(meeting.tags ?? []).map((t) => ({
            id: t.id,
            name: t.name,
            color: t.color,
          }))}
        />
      </div>
      {showUploadShortcut && (
        <button
          type="button"
          data-testid="meeting-card-upload-shortcut"
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            navigate({
              to: "/meetings/$id",
              params: { id: meeting.id },
              search: { action: "upload" } as never,
            });
          }}
          className="absolute bottom-3 right-3 z-10 inline-flex items-center gap-1 rounded-md border border-(--color-primary)/40 bg-(--color-card) px-2.5 py-1 text-xs font-medium text-(--color-primary) opacity-0 shadow-sm transition-opacity duration-150 group-hover:opacity-100 focus-visible:opacity-100 hover:bg-(--color-primary)/10"
        >
          <Upload className="size-3" aria-hidden />
          {t("meetings.kanban.uploadShortcut")}
        </button>
      )}
    </div>
  );
}
