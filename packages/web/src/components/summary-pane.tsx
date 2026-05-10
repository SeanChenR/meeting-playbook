/**
 * SummaryPane — slice-10 post-meeting summary tab body.
 *
 * Five visual states (per design.md Decision 6 + spec scenarios):
 *  1. Loading  — initial fetch in flight
 *  2. Pending  — backend has an in-flight task; React Query polls every 1s
 *  3. Done     — markdown body + status row + Regenerate + Export buttons
 *  4. Stale    — same as Done plus a stale-alert above the body
 *  5. Empty    — 404 (no row, not in flight) + "生成摘要" button
 *
 * Failed POST (409 summary.busy) shows an inline notice; the button
 * stays disabled until the next GET poll resolves.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type SummaryResponse,
  isPendingSummary,
  regenerateSummary,
  summaryQueryOptions,
} from "../lib/summary-api";
import { exportSummaryAsMarkdown } from "../lib/markdown-export";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MarkdownPreview } from "../lib/markdown-preview";
import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export interface SummaryPaneProps {
  meetingId: string;
  meeting: { title: string; created_at: string; status: string };
}

function _formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function SummaryPane({ meetingId, meeting }: SummaryPaneProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [postError, setPostError] = useState<string | null>(null);

  const query = useQuery(
    summaryQueryOptions(meetingId, {
      enabled: meeting.status === "completed",
      // React Query v5: refetchInterval callback receives the Query
      // instance (not just `data`). Read state.data off it. The earlier
      // `(data) => ...` signature was v4 — under v5 the Query object
      // never matches isPendingSummary, so polling never fired and the
      // pending-shape cache write was useless.
      refetchInterval: (q: { state: { data?: SummaryResponse } }) =>
        isPendingSummary(q.state.data) ? 1000 : false,
    }),
  );

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateSummary(meetingId),
    onSuccess: () => {
      setPostError(null);
      // Slice-10 race fix: write a pending shape into the cache immediately
      // so `refetchInterval` (which only polls when data shape is pending)
      // kicks in right away. Otherwise the next GET can land in a
      // false-negative window — backend's spawn_summary_task is still in
      // the asyncio scheduler queue, so `runtime.is_pending` returns
      // False and GET returns 404. That writes `null` to the cache,
      // refetchInterval returns `false`, polling never starts, and the
      // generation finishes silently with no UI update.
      queryClient.setQueryData(["summary", meetingId], {
        status: "pending",
        generated_at: null,
      });
    },
    onError: (err: unknown) => {
      // Map the SummaryApiError envelope to a localised message; fall back
      // to the unknown-error message for surprises.
      const code =
        err && typeof err === "object" && "errorCode" in err
          ? ((err as { errorCode?: string }).errorCode ?? "summary.generation_failed")
          : "summary.generation_failed";
      setPostError(localizedErrorMessage(code, t));
    },
  });

  const _trigger = () => {
    setPostError(null);
    regenerateMutation.mutate();
  };

  const data = query.data;
  const isLoading = query.isLoading;
  const isPending = isPendingSummary(data);
  const isMutating = regenerateMutation.isPending;

  return (
    <Card data-testid="summary-pane" className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>{t("meetings.summary.heading")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 overflow-y-auto">
        {/* Loading state */}
        {isLoading ? (
          <div
            data-testid="summary-loading"
            className="flex flex-1 items-center justify-center text-sm text-(--color-muted-foreground)"
          >
            {t("common.loading")}
          </div>
        ) : isPending ? (
          /* Pending state */
          <div
            data-testid="summary-pending"
            className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-(--color-muted-foreground)"
          >
            <p>{t("meetings.summary.generating")}</p>
            <p className="text-xs">{t("meetings.summary.generatingHint")}</p>
          </div>
        ) : data === null || data === undefined ? (
          /* Empty state (404) */
          <div
            data-testid="summary-empty"
            className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-(--color-muted-foreground)"
          >
            <p>{t("meetings.summary.emptyState")}</p>
            <Button
              type="button"
              data-testid="summary-generate-button"
              onClick={_trigger}
              disabled={isMutating}
            >
              {t("meetings.summary.generate")}
            </Button>
            {postError ? <p className="text-xs text-(--color-destructive)">{postError}</p> : null}
          </div>
        ) : (
          /* Done (with optional stale alert) */
          <>
            <div className="flex items-center justify-between gap-2 text-xs text-(--color-muted-foreground)">
              <span>
                {t("meetings.summary.generatedAt", {
                  at: _formatTimestamp(data.generated_at),
                })}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  data-testid="summary-regenerate-button"
                  onClick={_trigger}
                  disabled={isMutating}
                >
                  {t("meetings.summary.regenerate")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  data-testid="summary-export-button"
                  onClick={() => exportSummaryAsMarkdown(meeting, data.markdown)}
                >
                  {t("meetings.summary.exportMd")}
                </Button>
              </div>
            </div>
            {data.is_stale ? (
              <Alert data-testid="summary-stale-alert" variant="warning" role="note">
                {t("meetings.summary.staleAlert")}
              </Alert>
            ) : null}
            {postError ? <p className="text-xs text-(--color-destructive)">{postError}</p> : null}
            <MarkdownPreview source={data.markdown} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
