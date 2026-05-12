/**
 * MeetingPrevNextNav — slice meetings-ux-revamp task 5.1.
 *
 * Renders [← prev] [BackLink to /meetings] [next →] inside the
 * MetadataCard header so the user can flip between meeting detail
 * pages without bouncing back to the list.
 *
 * Sort order matches the user's mental model of the meeting backlog:
 * `scheduled_start_at` ASC, with undated meetings sorted to the end
 * (lexicographic `~` prefix exploits ASCII ordering — `~` is greater
 * than every ISO-8601 digit). Inside the undated tail, ordering falls
 * back to `created_at` ASC because the same lexicographic comparison
 * applies. That matches the calendar / Kanban surfaces' preference
 * for time-based ordering.
 *
 * Cache-only lookup per design Decision 2: this component reads the
 * existing React Query meetingsList cache and does NOT trigger a new
 * fetch. When the cache is empty (deep-link entry without first
 * visiting /meetings), both arrows render disabled with a localized
 * tooltip.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { BackLink } from "./back-link";
import { Button } from "./ui/button";
import { type Meeting, meetingsListQueryOptions } from "../lib/meetings-api";

export interface MeetingPrevNextNavProps {
  currentId: string;
}

function _sortKey(m: Meeting): string {
  // ASCII `~` is greater than every digit, so undated meetings sort
  // to the end. Inside the tail, created_at gives stable ordering.
  return m.scheduled_start_at ?? `~${m.created_at}`;
}

export function MeetingPrevNextNav({ currentId }: MeetingPrevNextNavProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const cached = queryClient.getQueryData<Meeting[]>(meetingsListQueryOptions().queryKey) ?? null;

  const sorted = cached ? [...cached].sort((a, b) => _sortKey(a).localeCompare(_sortKey(b))) : null;
  const idx = sorted?.findIndex((m) => m.id === currentId) ?? -1;
  const prev = sorted && idx > 0 ? sorted[idx - 1] : null;
  const next = sorted && idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;

  const disabledTooltip = t("meetings.detail.prevNextDisabled");

  return (
    <div data-testid="meeting-prev-next-nav" className="inline-flex items-center gap-1.5">
      {prev ? (
        <Link
          {...({ to: `/meetings/${prev.id}` } as { to: "/meetings/$id"; params: { id: string } })}
          data-testid="meeting-prev-link"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-(--color-muted-foreground) transition-colors hover:bg-(--color-muted) hover:text-(--color-foreground)"
          title={t("meetings.detail.prevTitle")}
        >
          <ChevronLeft className="size-4" />
        </Link>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled
          data-testid="meeting-prev-disabled"
          title={disabledTooltip}
          className="size-8 p-0"
        >
          <ChevronLeft className="size-4" />
        </Button>
      )}
      <BackLink to="/meetings" />
      {next ? (
        <Link
          {...({ to: `/meetings/${next.id}` } as { to: "/meetings/$id"; params: { id: string } })}
          data-testid="meeting-next-link"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-(--color-muted-foreground) transition-colors hover:bg-(--color-muted) hover:text-(--color-foreground)"
          title={t("meetings.detail.nextTitle")}
        >
          <ChevronRight className="size-4" />
        </Link>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled
          data-testid="meeting-next-disabled"
          title={disabledTooltip}
          className="size-8 p-0"
        >
          <ChevronRight className="size-4" />
        </Button>
      )}
    </div>
  );
}
