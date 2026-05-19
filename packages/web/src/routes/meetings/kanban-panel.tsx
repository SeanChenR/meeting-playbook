/**
 * MeetingsKanbanPanel — refactor-meetings-tabs-unified.
 *
 * Kanban view extracted from the old MeetingsList route. The wrapper
 * (MeetingsList) now owns ProtectedShell + MeetingsViewTabs and renders
 * this panel inside an AnimatePresence boundary, so the panel only owns
 * its header (title + actions) and the Kanban grid.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "@tanstack/react-router";
import { Calendar as CalendarIcon } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "../../components/animate-ui/icons/plus";
import { MeetingsKanban } from "../../components/meetings-kanban";
import { TagFilter } from "../../components/tags/tag-filter";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { meetingsListQueryOptions, MeetingApiError } from "../../lib/meetings-api";
import { resolveMeetingBucket } from "../../lib/meetings-bucket";

function _parseTagIdsFromSearch(searchStr: string): string[] {
  const params = new URLSearchParams(searchStr.startsWith("?") ? searchStr.slice(1) : searchStr);
  const raw = params.get("tag_ids");
  return raw ? raw.split(",").filter(Boolean) : [];
}

export function MeetingsKanbanPanel() {
  const { t } = useTranslation();
  const location = useLocation();
  const tagIds = useMemo(
    () => _parseTagIdsFromSearch(location.searchStr ?? ""),
    [location.searchStr],
  );
  const query = useQuery(meetingsListQueryOptions({ tagIds }));
  const meetings = query.data ?? null;
  const error = query.isError
    ? query.error instanceof MeetingApiError && query.error.errorCode
      ? localizedErrorMessage(query.error.errorCode, t)
      : t("errors.common.unknown")
    : null;

  const total = meetings?.length ?? 0;
  const bucketCounts = (meetings ?? []).reduce(
    (acc, m) => {
      acc[resolveMeetingBucket(m)] += 1;
      return acc;
    },
    { upcoming: 0, needs_recording: 0, completed: 0 },
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
            {t("meetings.list.heading")}
          </h1>
          {meetings && (
            <p
              className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-(--color-foreground)/75"
              data-testid="meetings-list-meta"
            >
              <span className="font-medium text-(--color-foreground)">
                {total} {t("meetings.list.metaTotalSuffix")}
              </span>
              <span aria-hidden className="text-(--color-border-strong)">
                ·
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="size-1.5 rounded-full bg-(--color-info)" />
                {t("meetings.list.metaBucketUpcoming")} {bucketCounts.upcoming}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="size-1.5 rounded-full bg-(--color-warning)" />
                {t("meetings.list.metaBucketNeedsRecording")} {bucketCounts.needs_recording}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="size-1.5 rounded-full bg-(--color-accent)" />
                {t("meetings.list.metaBucketCompleted")} {bucketCounts.completed}
              </span>
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <TagFilter />
          <Link
            to="/settings/integrations"
            className={buttonVariants({ variant: "secondary", size: "sm" })}
            data-testid="meetings-list-import-calendar"
          >
            <CalendarIcon className="size-3.5" />
            {t("meetings.list.fromCalendarButton")}
          </Link>
          <Link to="/meetings/new" className={buttonVariants({ size: "sm" })}>
            <Plus animateOnHover className="size-3.5" />
            {t("meetings.list.newButtonShort")}
          </Link>
        </div>
      </header>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-(--color-destructive)">{error}</CardContent>
        </Card>
      )}

      {meetings === null && !error && (
        <p className="text-sm text-(--color-muted-foreground)">{t("common.loading")}</p>
      )}

      {meetings && meetings.length === 0 && (
        <Card data-testid="meetings-empty-state">
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <p className="text-base font-medium text-(--color-foreground)">
              {t("meetings.list.empty")}
            </p>
            <p className="max-w-sm text-sm text-(--color-muted-foreground)">
              {t("meetings.list.emptyHint")}
            </p>
          </CardContent>
        </Card>
      )}

      {meetings && meetings.length > 0 && <MeetingsKanban meetings={meetings} />}
    </div>
  );
}
