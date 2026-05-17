/**
 * MeetingLinkPicker — slice-21 task 5.1.
 *
 * Modal that lets the user pick a meeting to link to the current one.
 *
 * Behaviour (per spec "MeetingLinkPicker filters out the current meeting
 * and already-linked meetings from a cached meetings list"):
 *   - Reads `meetingsListQueryOptions().queryKey` from the React Query cache;
 *     does NOT issue a fresh fetch.
 *   - Filters out: (a) the current meeting; (b) every meeting whose id
 *     appears as `other_meeting_id` in the existing-links prop;
 *     (c) titles that don't match the typeahead substring.
 *   - On confirm: calls `useCreateLinkMutation` and closes the modal on
 *     success; on failure keeps the modal open and surfaces the
 *     localised error message via `localizedErrorMessage`.
 *   - Cache miss: render `meetings.links.picker.cacheMiss` hint + link
 *     to the meetings list route. No backfill fetch.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { localizedErrorMessage } from "../lib/i18n-errors";
import {
  type MeetingLinkApiError,
  type MeetingLinkView,
  useCreateLinkMutation,
} from "../lib/meeting-links-api";
import { type Meeting, meetingsListQueryOptions } from "../lib/meetings-api";

export interface MeetingLinkPickerProps {
  currentMeetingId: string;
  existingLinks: MeetingLinkView[];
  onClose: () => void;
}

function _formatScheduledTime(iso: string | null, locale: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MeetingLinkPicker({
  currentMeetingId,
  existingLinks,
  onClose,
}: MeetingLinkPickerProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const createMutation = useCreateLinkMutation(currentMeetingId);

  const cached = queryClient.getQueryData<Meeting[]>(meetingsListQueryOptions().queryKey);
  const cacheMiss = cached === undefined;

  const candidates = useMemo<Meeting[]>(() => {
    if (!cached) return [];
    const excluded = new Set<string>([currentMeetingId]);
    for (const link of existingLinks) {
      excluded.add(link.other_meeting_id);
    }
    const needle = query.trim().toLowerCase();
    return cached.filter((m) => {
      if (excluded.has(m.id)) return false;
      if (!needle) return true;
      return m.title.toLowerCase().includes(needle);
    });
  }, [cached, currentMeetingId, existingLinks, query]);

  function handleConfirm() {
    if (selectedId === null) return;
    setErrorMessage(null);
    createMutation.mutate(selectedId, {
      onSuccess: () => {
        onClose();
      },
      onError: (err) => {
        const errorCode = (err as MeetingLinkApiError).errorCode ?? "common.unknown";
        setErrorMessage(localizedErrorMessage(errorCode, t));
      },
    });
  }

  return (
    <Dialog open={true} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent className="max-w-lg">
        <div data-testid="meeting-link-picker">
          <DialogHeader>
            <DialogTitle>{t("meetings.links.addButton")}</DialogTitle>
          </DialogHeader>

          {cacheMiss ? (
            <div className="flex flex-col gap-2" data-testid="meeting-link-picker-cache-miss">
              <p className="text-sm text-(--color-muted-foreground)">
                {t("meetings.links.picker.cacheMiss")}
              </p>
              <Link
                {...({ to: "/meetings" } as { to: "/meetings" })}
                data-testid="meeting-link-picker-cache-miss-link"
                className="text-sm text-(--color-primary) hover:underline"
              >
                {t("nav.meetings")}
              </Link>
              <div className="mt-3 flex justify-end gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                  {t("meetings.links.picker.cancelButton")}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <Input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("meetings.links.picker.placeholder")}
                data-testid="meeting-link-picker-search"
              />

              <ul
                className="max-h-64 overflow-y-auto rounded-md border border-(--color-border)"
                data-testid="meeting-link-picker-list"
              >
                {candidates.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-(--color-muted-foreground)">
                    {t("meetings.links.empty")}
                  </li>
                ) : (
                  candidates.map((m) => (
                    <li key={m.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(m.id)}
                        data-testid={`meeting-link-picker-row-${m.id}`}
                        className={
                          selectedId === m.id
                            ? "flex w-full items-center justify-between gap-2 bg-(--color-primary)/10 px-3 py-2 text-left text-sm"
                            : "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-(--color-muted)/60"
                        }
                      >
                        <span className="truncate font-medium">{m.title}</span>
                        <span className="shrink-0 text-xs text-(--color-muted-foreground)">
                          {_formatScheduledTime(m.scheduled_start_at, i18n.language)}
                        </span>
                      </button>
                    </li>
                  ))
                )}
              </ul>

              {errorMessage && (
                <p
                  role="alert"
                  data-testid="meeting-link-picker-error"
                  className="text-sm text-(--color-destructive)"
                >
                  {errorMessage}
                </p>
              )}

              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                  {t("meetings.links.picker.cancelButton")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={selectedId === null || createMutation.isPending}
                  onClick={handleConfirm}
                  data-testid="meeting-link-picker-confirm"
                >
                  {t("meetings.links.picker.confirmButton")}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
