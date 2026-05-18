/**
 * Recordings index — P4 IA refactor task 2.2.
 *
 * Lists every Recording inside the active Recording window owned by the
 * current user, paginated by 25, filterable by free-text meeting title /
 * date range, with single + batch download. URL query state
 * (`since`/`until`/`search`/`page`) is the source of truth for filters so
 * the page is bookmarkable and back-button friendly.
 *
 * Single download reuses the existing per-meeting audio endpoint via the
 * `recordingAudioUrl` helper; batch download POSTs to the new
 * `/api/recordings/batch-download` endpoint. Failure modes (410 / 413 /
 * 422 / 403) surface as localized toasts via `localizedErrorMessage`.
 */

import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ProtectedShell } from "../../components/protected-shell";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  RecordingApiError,
  useBatchDownloadMutation,
  useRecordingsList,
  recordingAudioUrl,
  type RecordingListParams,
  type RecordingStream,
  type RecordingSummary,
} from "../../lib/recordings-api";

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 300;

interface ParsedQuery {
  since: string | undefined;
  until: string | undefined;
  search: string | undefined;
  page: number;
}

function _parseQuery(searchStr: string | undefined): ParsedQuery {
  const params = new URLSearchParams(
    searchStr && searchStr.startsWith("?") ? searchStr.slice(1) : (searchStr ?? ""),
  );
  const pageRaw = Number.parseInt(params.get("page") ?? "1", 10);
  return {
    since: params.get("since") ?? undefined,
    until: params.get("until") ?? undefined,
    search: params.get("search") ?? undefined,
    page: Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1,
  };
}

function _stringifyParams(p: ParsedQuery): Record<string, string> {
  const out: Record<string, string> = {};
  if (p.since) out.since = p.since;
  if (p.until) out.until = p.until;
  if (p.search) out.search = p.search;
  if (p.page !== 1) out.page = String(p.page);
  return out;
}

function _formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function _formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function _formatTimestamp(iso: string, locale: string): string {
  try {
    return new Date(iso).toLocaleString(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function RecordingsIndex() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const parsed = useMemo(() => _parseQuery(location.searchStr ?? ""), [location.searchStr]);

  const [searchDraft, setSearchDraft] = useState(parsed.search ?? "");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep the search draft in sync when the URL changes externally (back-button,
  // direct nav). Avoid clobbering a draft mid-typing by syncing only when the
  // committed value differs.
  useEffect(() => {
    setSearchDraft(parsed.search ?? "");
  }, [parsed.search]);

  const updateParams = (next: Partial<ParsedQuery>) => {
    const merged: ParsedQuery = {
      since: next.since !== undefined ? next.since || undefined : parsed.since,
      until: next.until !== undefined ? next.until || undefined : parsed.until,
      search: next.search !== undefined ? next.search || undefined : parsed.search,
      page: next.page ?? 1,
    };
    navigate({
      to: "/recordings",
      search: _stringifyParams(merged) as unknown as Record<string, never>,
    });
  };

  const handleSearchChange = (value: string) => {
    setSearchDraft(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      updateParams({ search: value, page: 1 });
    }, SEARCH_DEBOUNCE_MS);
  };

  const queryParams: RecordingListParams = {
    since: parsed.since,
    until: parsed.until,
    search: parsed.search,
    page: parsed.page,
  };
  const listQuery = useRecordingsList(queryParams);
  const batchDownload = useBatchDownloadMutation();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const recordings = listQuery.data?.recordings ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = total === 0 ? 1 : Math.ceil(total / PAGE_SIZE);
  const allSelectedOnPage = recordings.length > 0 && recordings.every((r) => selected.has(r.id));

  const toggleAllOnPage = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allSelectedOnPage) {
        for (const r of recordings) next.delete(r.id);
      } else {
        for (const r of recordings) next.add(r.id);
      }
      return next;
    });
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBatchDownload = () => {
    if (selected.size === 0) return;
    const ids = Array.from(selected);
    batchDownload.mutate(
      { recording_ids: ids },
      {
        onSuccess: () => {
          toast.success(t("recordings.list.batch.zipReady"));
          setSelected(new Set());
        },
        onError: (err) => {
          const apiErr = err instanceof RecordingApiError ? err : null;
          const code = apiErr?.errorCode;
          if (code === "recording.batch_oversize") {
            toast.error(localizedErrorMessage(code, t, { limit: _formatBytes(2_147_483_648) }));
          } else if (code === "recording.retention_expired") {
            toast.error(localizedErrorMessage(code, t, { count: ids.length }));
            // The server's view of the window may have advanced; refetch.
            void listQuery.refetch();
          } else if (code) {
            toast.error(localizedErrorMessage(code, t));
          } else {
            toast.error(t("errors.common.unknown"));
          }
        },
      },
    );
  };

  const listErrorMessage =
    listQuery.error instanceof RecordingApiError && listQuery.error.errorCode
      ? localizedErrorMessage(listQuery.error.errorCode, t)
      : listQuery.isError
        ? t("recordings.list.loadError")
        : null;

  return (
    <ProtectedShell>
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
          {t("recordings.list.heading")}
        </h1>
        <p className="text-sm text-(--color-muted-foreground)">{t("recordings.list.subheading")}</p>
      </header>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
            <Input
              type="search"
              value={searchDraft}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder={t("recordings.list.searchPlaceholder")}
              aria-label={t("recordings.list.searchPlaceholder")}
              data-testid="recordings-search-input"
            />
            <div className="flex items-center gap-2">
              <label className="text-xs text-(--color-muted-foreground)" htmlFor="rec-since">
                {t("recordings.list.dateRange.since")}
              </label>
              <Input
                id="rec-since"
                type="date"
                value={parsed.since ?? ""}
                onChange={(e) => updateParams({ since: e.target.value, page: 1 })}
                data-testid="recordings-since-input"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-(--color-muted-foreground)" htmlFor="rec-until">
                {t("recordings.list.dateRange.until")}
              </label>
              <Input
                id="rec-until"
                type="date"
                value={parsed.until ?? ""}
                onChange={(e) => updateParams({ until: e.target.value, page: 1 })}
                data-testid="recordings-until-input"
              />
            </div>
          </div>

          {selected.size > 0 && (
            <div
              className="flex items-center justify-between rounded-md border border-(--color-border) bg-(--color-muted)/40 px-3 py-2"
              data-testid="recordings-batch-bar"
            >
              <span className="text-sm">
                {t("recordings.list.batch.selectedCount", { count: selected.size })}
              </span>
              <Button
                size="sm"
                onClick={handleBatchDownload}
                disabled={batchDownload.isPending}
                data-testid="recordings-batch-download"
              >
                {t("recordings.list.batch.confirm")}
              </Button>
            </div>
          )}

          {listQuery.isPending && (
            <div className="py-10 text-center text-sm text-(--color-muted-foreground)">
              {t("recordings.list.loading")}
            </div>
          )}

          {listErrorMessage && (
            <div className="py-10 text-center text-sm text-(--color-destructive)">
              {listErrorMessage}
            </div>
          )}

          {!listQuery.isPending && !listErrorMessage && recordings.length === 0 && (
            <div className="space-y-2 py-12 text-center" data-testid="recordings-empty-state">
              <p className="text-base font-medium text-(--color-foreground)">
                {t("recordings.list.empty")}
              </p>
              <p className="text-sm text-(--color-muted-foreground)">
                {t("recordings.list.emptyExpiredHint")}
              </p>
            </div>
          )}

          {!listQuery.isPending && recordings.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-(--color-border) text-left text-xs uppercase tracking-wider text-(--color-muted-foreground)">
                    <th className="w-8 px-2 py-2">
                      <input
                        type="checkbox"
                        checked={allSelectedOnPage}
                        onChange={toggleAllOnPage}
                        aria-label={t("recordings.list.action.selectAll")}
                        data-testid="recordings-select-all"
                      />
                    </th>
                    <th className="px-2 py-2">{t("recordings.list.columns.date")}</th>
                    <th className="px-2 py-2">{t("recordings.list.columns.meeting")}</th>
                    <th className="px-2 py-2">{t("recordings.list.columns.counterparty")}</th>
                    <th className="px-2 py-2">{t("recordings.list.columns.duration")}</th>
                    <th className="px-2 py-2">{t("recordings.list.columns.size")}</th>
                    <th className="px-2 py-2">{t("recordings.list.columns.stream")}</th>
                    <th className="px-2 py-2 text-right">{t("recordings.list.columns.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {recordings.map((r) => (
                    <RecordingRow
                      key={r.id}
                      row={r}
                      checked={selected.has(r.id)}
                      onToggle={() => toggleOne(r.id)}
                      locale={i18n.language}
                      t={t}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between gap-3 border-t border-(--color-border) pt-3 text-sm text-(--color-muted-foreground)">
              <span>
                {t("recordings.list.pagination.status", {
                  page: parsed.page,
                  total: totalPages,
                })}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={parsed.page <= 1}
                  onClick={() => updateParams({ page: parsed.page - 1 })}
                  data-testid="recordings-page-prev"
                >
                  {t("recordings.list.pagination.previous")}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={parsed.page >= totalPages}
                  onClick={() => updateParams({ page: parsed.page + 1 })}
                  data-testid="recordings-page-next"
                >
                  {t("recordings.list.pagination.next")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </ProtectedShell>
  );
}

interface RowProps {
  row: RecordingSummary;
  checked: boolean;
  onToggle: () => void;
  locale: string;
  t: (key: string, opts?: Record<string, unknown>) => string;
}

function RecordingRow({ row, checked, onToggle, locale, t }: RowProps) {
  const streamKey: RecordingStream = row.stream;
  return (
    <tr className="border-b border-(--color-border)/60 hover:bg-(--color-muted)/30">
      <td className="px-2 py-3">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={`select-${row.id}`}
          data-testid={`recordings-row-checkbox-${row.id}`}
        />
      </td>
      <td className="px-2 py-3 whitespace-nowrap text-(--color-foreground)">
        {_formatTimestamp(row.captured_at, locale)}
      </td>
      <td className="px-2 py-3">
        <Link
          to={`/meetings/${row.meeting_id}` as "/meetings/$id"}
          className="text-(--color-primary) underline-offset-4 hover:underline"
          data-testid={`recordings-row-meeting-${row.id}`}
        >
          {row.meeting_title}
        </Link>
      </td>
      <td className="px-2 py-3 text-(--color-muted-foreground)">{row.counterparty_label}</td>
      <td className="px-2 py-3 tabular-nums">{_formatDuration(row.duration_ms)}</td>
      <td className="px-2 py-3 tabular-nums">{_formatBytes(row.byte_size)}</td>
      <td className="px-2 py-3">
        <Badge variant={streamKey === "me" ? "success" : "outline"}>
          {t(`recordings.list.streamBadge.${streamKey}`)}
        </Badge>
      </td>
      <td className="px-2 py-3 text-right">
        <a
          href={recordingAudioUrl(row.meeting_id, row.id)}
          download
          className="text-sm text-(--color-primary) underline-offset-4 hover:underline"
          data-testid={`recordings-row-download-${row.id}`}
        >
          {t("recordings.list.action.download")}
        </a>
      </td>
    </tr>
  );
}
