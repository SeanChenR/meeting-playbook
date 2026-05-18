/**
 * Meetings list — slice meetings-ux-revamp tasks 2.3 + 3.2.
 *
 * Visual shape:
 *   - Page header (title + meta)
 *   - Right controls: Calendar 匯入 + 新會議
 *   - Shared <MeetingsViewTabs value="kanban" /> (task 3.2 mounts it)
 *   - <MeetingsKanban> grouped by date bucket
 *
 * The previous auto-fill grid + inline `<Tabs>` block are removed —
 * Kanban replaces the grid; MeetingsViewTabs replaces the inline tabs.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "@tanstack/react-router";
import { Calendar as CalendarIcon } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "../../components/animate-ui/icons/plus";
import { MeetingsKanban } from "../../components/meetings-kanban";
import { MeetingsViewTabs } from "../../components/meetings-view-tabs";
import { ProtectedShell } from "../../components/protected-shell";
import { TagFilter } from "../../components/tags/tag-filter";
import { buttonVariants } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { meetingsListQueryOptions, MeetingApiError } from "../../lib/meetings-api";

function _parseTagIdsFromSearch(searchStr: string): string[] {
  const params = new URLSearchParams(searchStr.startsWith("?") ? searchStr.slice(1) : searchStr);
  const raw = params.get("tag_ids");
  return raw ? raw.split(",").filter(Boolean) : [];
}

export function MeetingsList() {
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
  const upcoming = meetings?.filter((m) => m.status !== "completed").length ?? 0;

  return (
    <ProtectedShell>
      {/* Post-apply Q2 fix: header is a 3-slot row — title (left)
          / MeetingsViewTabs (centred) / action cluster (right). The
          centred slot is mirrored on /meetings/calendar so toggling
          views doesn't shuffle the tab position. */}
      <header className="grid grid-cols-1 items-center gap-4 lg:grid-cols-[1fr_auto_1fr]">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
            {t("meetings.list.heading")}
          </h1>
          {meetings && (
            <p className="text-sm text-(--color-muted-foreground)">
              {t("meetings.list.metaSummary", { total, upcoming })}
            </p>
          )}
        </div>
        <div className="flex justify-center">
          <MeetingsViewTabs value="kanban" />
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
    </ProtectedShell>
  );
}
