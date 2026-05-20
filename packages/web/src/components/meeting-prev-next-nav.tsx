/**
 * MeetingPrevNextNav — single thin row containing three groups (refactor-meeting-detail-three-column):
 *
 *   [ArrowLeft] 會議列表   │   [ChevronLeft] 上一場 「...」 / 下一場 「...」 [ChevronRight]
 *
 * The leftmost back-to-list link reuses the shared <BackLink> primitive
 * (Lucide ArrowLeft). A vertical divider separates parent navigation
 * from lateral (prev / next) navigation. The icon weight contrast
 * (ArrowLeft thicker vs ChevronLeft/Right thinner) signals "up vs sideways".
 *
 * Sort order: meetings sorted by `scheduled_start_at ASC`, undated meetings
 * sorted to the end via lexicographic `~` prefix.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type Meeting, meetingsListQueryOptions } from "../lib/meetings-api";
import { BackLink } from "./back-link";
import { Button } from "./ui/button";

export interface MeetingPrevNextNavProps {
  currentId: string;
}

function _sortKey(m: Meeting): string {
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
    <div data-testid="meeting-prev-next-nav" className="inline-flex items-center gap-3">
      <BackLink to="/meetings" labelKey="meetings.detail.backToList" />
      <span
        data-testid="meeting-prev-next-divider"
        aria-hidden
        className="h-3 w-px bg-(--color-border)"
      />
      <div className="inline-flex items-center gap-1.5">
        {prev ? (
          <Link
            {...({ to: `/meetings/${prev.id}` } as { to: "/meetings/$id"; params: { id: string } })}
            data-testid="meeting-prev-link"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-(--color-muted-foreground) transition-colors hover:bg-(--color-muted) hover:text-(--color-foreground)"
            title={t("meetings.detail.prevTitle")}
          >
            <ChevronLeft className="size-4" strokeWidth={1.5} />
            <span className="max-w-[160px] truncate text-xs">{prev.title}</span>
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
            <ChevronLeft className="size-4" strokeWidth={1.5} />
          </Button>
        )}
        <span aria-hidden className="text-xs text-(--color-muted-foreground)">
          /
        </span>
        {next ? (
          <Link
            {...({ to: `/meetings/${next.id}` } as { to: "/meetings/$id"; params: { id: string } })}
            data-testid="meeting-next-link"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-(--color-muted-foreground) transition-colors hover:bg-(--color-muted) hover:text-(--color-foreground)"
            title={t("meetings.detail.nextTitle")}
          >
            <span className="max-w-[160px] truncate text-xs">{next.title}</span>
            <ChevronRight className="size-4" strokeWidth={1.5} />
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
            <ChevronRight className="size-4" strokeWidth={1.5} />
          </Button>
        )}
      </div>
    </div>
  );
}
