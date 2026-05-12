/**
 * MeetingsKanban — slice meetings-ux-revamp tasks 2.2 + 2.3
 * + post-apply Q1 fix (past column collapse).
 *
 * 3-column date-bucketed list of meetings. Buckets come from the pure
 * `getMeetingDateBucket` helper; Kanban groups + renders.
 *
 * Past column trims to the most recent N (default 5) by default and
 * shows a "顯示全部 (N)" toggle so the column doesn't grow unbounded
 * as the meeting backlog accumulates. Past meetings are sorted by
 * `scheduled_start_at` DESC so the most recent ones float up.
 *
 * Layout: equal-width columns with min-width 280px so cards never wrap.
 * Each column body scrolls vertically when overflowing.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { getMeetingDateBucket, type MeetingDateBucket } from "../lib/meetings-bucket";
import type { Meeting } from "../lib/meetings-api";
import { MeetingCard } from "./meeting-card";
import { Badge } from "./ui/badge";

export interface MeetingsKanbanProps {
  meetings: Meeting[];
}

const BUCKET_ORDER: MeetingDateBucket[] = ["upcoming", "future", "past"];

const BUCKET_LABEL_KEY: Record<MeetingDateBucket, string> = {
  upcoming: "meetings.kanban.bucketUpcoming",
  future: "meetings.kanban.bucketFuture",
  past: "meetings.kanban.bucketPast",
};

const PAST_COLLAPSED_LIMIT = 5;

function _sortPastDesc(meetings: Meeting[]): Meeting[] {
  return [...meetings].sort((a, b) => {
    const aKey = a.scheduled_start_at ?? a.created_at;
    const bKey = b.scheduled_start_at ?? b.created_at;
    return bKey.localeCompare(aKey);
  });
}

export function MeetingsKanban({ meetings }: MeetingsKanbanProps) {
  const { t } = useTranslation();
  const [pastExpanded, setPastExpanded] = useState(false);

  const grouped = useMemo(() => {
    const now = new Date();
    const buckets: Record<MeetingDateBucket, Meeting[]> = {
      upcoming: [],
      future: [],
      past: [],
    };
    for (const m of meetings) {
      buckets[getMeetingDateBucket(m, now)].push(m);
    }
    buckets.past = _sortPastDesc(buckets.past);
    return buckets;
  }, [meetings]);

  return (
    <div
      data-testid="meetings-kanban"
      className="grid h-full min-h-0 gap-3"
      style={{ gridTemplateColumns: "repeat(3, minmax(280px, 1fr))" }}
    >
      {BUCKET_ORDER.map((bucket) => {
        const items = grouped[bucket];
        const isPast = bucket === "past";
        const isOverLimit = isPast && items.length > PAST_COLLAPSED_LIMIT;
        const visible = isOverLimit && !pastExpanded ? items.slice(0, PAST_COLLAPSED_LIMIT) : items;
        return (
          <section
            key={bucket}
            data-testid={`kanban-column-${bucket}`}
            className="flex min-h-0 flex-col rounded-lg border border-(--color-border) bg-(--color-card)/40"
          >
            <header className="flex items-center justify-between border-b border-(--color-border) px-3.5 py-2.5">
              <p className="text-sm font-semibold text-(--color-foreground)">
                {t(BUCKET_LABEL_KEY[bucket])}
              </p>
              <Badge variant="outline" data-testid={`kanban-count-${bucket}`}>
                {items.length}
              </Badge>
            </header>
            <div
              data-testid={`kanban-body-${bucket}`}
              className="flex flex-1 flex-col gap-2.5 overflow-y-auto p-3"
              style={{ maxHeight: "calc(100dvh - 280px)" }}
            >
              {items.length === 0 ? (
                <p
                  data-testid={`kanban-empty-${bucket}`}
                  className="flex flex-1 items-center justify-center text-center text-xs text-(--color-muted-foreground)"
                >
                  {t("meetings.kanban.bucketEmpty")}
                </p>
              ) : (
                <>
                  {visible.map((m) => (
                    <MeetingCard key={m.id} meeting={m} />
                  ))}
                  {isOverLimit && (
                    <button
                      type="button"
                      data-testid="kanban-past-toggle"
                      onClick={() => setPastExpanded((v) => !v)}
                      className="rounded-md border border-dashed border-(--color-border) px-3 py-2 text-xs text-(--color-muted-foreground) transition-colors hover:border-(--color-primary)/40 hover:text-(--color-foreground)"
                    >
                      {pastExpanded
                        ? t("meetings.kanban.pastCollapse")
                        : t("meetings.kanban.pastShowAll", { count: items.length })}
                    </button>
                  )}
                </>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
