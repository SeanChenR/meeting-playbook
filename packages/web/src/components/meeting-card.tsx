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

import { Link } from "@tanstack/react-router";
import { Calendar as CalendarIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "./ui/badge";
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

function _durationMinutes(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
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
}

export function MeetingCard({ meeting }: MeetingCardProps) {
  const { t, i18n } = useTranslation();
  const color = STATUS_COLOR[meeting.status];
  const badgeVariant = STATUS_BADGE[meeting.status];
  const duration = _durationMinutes(meeting.scheduled_start_at, meeting.scheduled_end_at);
  const timeText = meeting.scheduled_start_at
    ? _formatTime(meeting.scheduled_start_at, i18n.language)
    : _formatTime(meeting.created_at, i18n.language);

  return (
    <Link
      // Literal-path form: bypasses typed param resolution so the synthetic
      // test router renders an absolute href without the detail route in
      // its tree. Production runtime accepts both forms.
      {...({ to: `/meetings/${meeting.id}` } as { to: "/meetings/$id"; params: { id: string } })}
      data-testid="meeting-card"
      // Post-apply fix: removed `h-full` (was for auto-fill grid
      // equal-height) AND added `shrink-0` because the Kanban column
      // body is a `flex flex-col max-h-...` container — without
      // shrink-0, flex's default shrink rule clips card content
      // (counterparty + date hidden) when many cards stack. shrink-0
      // forces natural card height; column overflow-y scrolls instead.
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
}
