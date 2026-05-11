/**
 * SummaryPane — slice ui-overhaul-claude-design task 6.5.
 *
 * Visual contract aligned with design bundle `SummaryPane`:
 *   - 2-col grid: main (1fr) + sidebar (280px)
 *   - Main: header (Sparkles icon + "AI 摘要" + vN · time badge +
 *           3 action buttons) + markdown body
 *   - Sidebar Card: KV metadata rows + keyword Badge list + Sparkles
 *                   info Alert
 *
 * Per Decision 7 the data-source surface stays at the slice-10 contract
 * (markdown, generated_at, is_stale) — duration / ASR / keyword fields
 * aren't on the API yet, so the sidebar renders an empty-state placeholder
 * for those rows. They light up automatically when the backend grows them.
 *
 * Preserves all five existing states (loading / pending / done / stale /
 * empty) + the regenerate POST + export-as-markdown flow. Test contract is
 * extended for the new structural testids; existing assertions stay green.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, RefreshCw, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { exportSummaryAsMarkdown } from "../lib/markdown-export";
import { MarkdownPreview } from "../lib/markdown-preview";
import {
  type SummaryResponse,
  isPendingSummary,
  regenerateSummary,
  summaryQueryOptions,
} from "../lib/summary-api";
import { Alert } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Separator } from "./ui/separator";

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
  const [copied, setCopied] = useState(false);

  const query = useQuery(
    summaryQueryOptions(meetingId, {
      enabled: meeting.status === "completed",
      refetchInterval: (q: { state: { data?: SummaryResponse } }) =>
        isPendingSummary(q.state.data) ? 1000 : false,
    }),
  );

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateSummary(meetingId),
    onSuccess: () => {
      setPostError(null);
      queryClient.setQueryData(["summary", meetingId], {
        status: "pending",
        generated_at: null,
      });
    },
    onError: (err: unknown) => {
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

  const _copy = async (markdown: string) => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard write may be blocked; silent fallback.
    }
  };

  const data = query.data;
  const isLoading = query.isLoading;
  const isPending = isPendingSummary(data);
  const isMutating = regenerateMutation.isPending;
  const isDone = data && !isPending && "markdown" in data;

  return (
    <div
      data-testid="summary-pane"
      className="grid h-full min-h-0 gap-4"
      style={{ gridTemplateColumns: "minmax(0, 1fr) 280px" }}
    >
      <Card
        data-testid="summary-pane-main"
        className="flex h-full min-h-0 flex-col overflow-hidden"
      >
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-(--color-border) px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-(--color-primary)" aria-hidden />
            <span className="text-sm font-semibold text-(--color-foreground)">
              {t("meetings.summary.aiHeading")}
            </span>
            {isDone && data && (
              <Badge variant="default" data-testid="summary-version-badge">
                {_formatTimestamp(data.generated_at)}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              data-testid="summary-regenerate-button"
              onClick={_trigger}
              disabled={isMutating}
            >
              <RefreshCw className="size-3" />
              {t("meetings.summary.regenerate")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              data-testid="summary-copy-button"
              onClick={() => isDone && data && _copy(data.markdown)}
              disabled={!isDone}
            >
              <Copy className="size-3" />
              {copied ? t("meetings.summary.copied") : t("meetings.summary.copy")}
            </Button>
            <Button
              type="button"
              size="sm"
              data-testid="summary-export-button"
              onClick={() => isDone && data && exportSummaryAsMarkdown(meeting, data.markdown)}
              disabled={!isDone}
            >
              <Download className="size-3" />
              {t("meetings.summary.exportMd")}
            </Button>
          </div>
        </header>

        <CardContent className="flex flex-1 min-h-0 flex-col gap-3 overflow-y-auto p-5">
          {isLoading ? (
            <SummaryState testId="summary-loading">{t("common.loading")}</SummaryState>
          ) : isPending ? (
            <SummaryState testId="summary-pending" hint={t("meetings.summary.generatingHint")}>
              {t("meetings.summary.generating")}
            </SummaryState>
          ) : data === null || data === undefined ? (
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
              {postError && <p className="text-xs text-(--color-destructive)">{postError}</p>}
            </div>
          ) : (
            <>
              {data.is_stale && (
                <Alert data-testid="summary-stale-alert" variant="warning" role="note">
                  {t("meetings.summary.staleAlert")}
                </Alert>
              )}
              {postError && <p className="text-xs text-(--color-destructive)">{postError}</p>}
              <MarkdownPreview source={data.markdown} />
            </>
          )}
        </CardContent>
      </Card>

      <Card data-testid="summary-pane-sidebar">
        <CardContent className="space-y-3 p-4">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-(--color-foreground)">
              {t("meetings.summary.sidebarMeta")}
            </p>
            <dl
              data-testid="summary-sidebar-kv"
              className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm"
            >
              <dt className="text-(--color-muted-foreground)">
                {t("meetings.summary.metaCreatedAt")}
              </dt>
              <dd className="text-right font-medium">{_formatTimestamp(meeting.created_at)}</dd>
              <dt className="text-(--color-muted-foreground)">
                {t("meetings.summary.metaStatus")}
              </dt>
              <dd className="text-right font-medium">{t(`meetings.status.${meeting.status}`)}</dd>
              <dt className="text-(--color-muted-foreground)">
                {t("meetings.summary.metaGeneratedAt")}
              </dt>
              <dd className="text-right font-medium">
                {isDone && data ? _formatTimestamp(data.generated_at) : "—"}
              </dd>
            </dl>
          </div>

          <Separator />

          <div className="space-y-2">
            <p className="text-sm font-semibold text-(--color-foreground)">
              {t("meetings.summary.sidebarKeywords")}
            </p>
            <div data-testid="summary-sidebar-keywords" className="flex flex-wrap gap-1.5">
              {/* Backend doesn't ship keywords yet; placeholder badge keeps
                  the structural slot visible. Replaces with real chips when
                  the API surfaces them. */}
              <Badge variant="outline">{t("meetings.summary.keywordsEmpty")}</Badge>
            </div>
          </div>

          <Separator />

          <Alert variant="default" data-testid="summary-sidebar-info">
            <div className="flex items-start gap-2">
              <Sparkles className="mt-0.5 size-3.5 text-(--color-primary)" aria-hidden />
              <p className="text-xs text-(--color-muted-foreground)">
                {t("meetings.summary.sidebarInfo")}
              </p>
            </div>
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryState({
  testId,
  hint,
  children,
}: {
  testId: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div
      data-testid={testId}
      className="flex flex-1 flex-col items-center justify-center gap-1 text-sm text-(--color-muted-foreground)"
    >
      <p>{children}</p>
      {hint && <p className="text-xs">{hint}</p>}
    </div>
  );
}
