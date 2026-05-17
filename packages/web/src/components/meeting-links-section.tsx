/**
 * MeetingLinksSection — slice-21 task 4.2.
 *
 * Renders the list of related-meeting links inside the MetadataCard header.
 * Reads `meetingLinksQueryOptions(meetingId)` and supports collapse > 10
 * links (per spec "Collapse triggers when link count exceeds ten").
 *
 * Behaviour:
 *   - Empty state: render heading + `meetings.links.empty` + add button.
 *   - 1+ links:   render heading + count + list + delete icon per row +
 *                 add button.
 *   - > 10 links: collapsed to first 10 with `meetings.links.showMore`
 *                 toggle; clicking switches to `meetings.links.showFewer`.
 *   - Add button opens `<MeetingLinkPicker>` modal.
 *   - Delete icon triggers `useDeleteLinkMutation` immediately (no confirm
 *     — the row is recoverable by re-linking).
 *
 * Per UI conventions: no emojis in strings; lucide icons for static UX.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { MeetingLinkPicker } from "./meeting-link-picker";
import { Button } from "./ui/button";
import {
  meetingLinksQueryOptions,
  useDeleteLinkMutation,
  type MeetingLinkView,
} from "../lib/meeting-links-api";

export interface MeetingLinksSectionProps {
  meetingId: string;
}

const COLLAPSE_THRESHOLD = 10;

function _formatScheduledTime(iso: string, locale: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MeetingLinksSection({ meetingId }: MeetingLinksSectionProps) {
  const { t, i18n } = useTranslation();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const linksQuery = useQuery(meetingLinksQueryOptions(meetingId));
  const deleteMutation = useDeleteLinkMutation(meetingId);

  const links: MeetingLinkView[] = linksQuery.data ?? [];
  const overThreshold = links.length > COLLAPSE_THRESHOLD;
  const visibleLinks = overThreshold && !expanded ? links.slice(0, COLLAPSE_THRESHOLD) : links;

  return (
    <div
      data-testid="meeting-links-section"
      className="flex flex-col gap-2 rounded-md border border-(--color-border) bg-(--color-muted)/30 p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-(--color-foreground)">
            {t("meetings.links.heading")}
          </span>
          {links.length > 0 && (
            <span className="text-xs text-(--color-muted-foreground)">
              {t("meetings.links.count", { count: links.length })}
            </span>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setPickerOpen(true)}
          data-testid="meeting-links-add-button"
        >
          {t("meetings.links.addButton")}
        </Button>
      </div>

      {links.length === 0 ? (
        <p data-testid="meeting-links-empty" className="text-xs text-(--color-muted-foreground)">
          {t("meetings.links.empty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {visibleLinks.map((link) => (
            <li
              key={link.link_id}
              className="flex items-center justify-between gap-2 rounded-md px-2 py-1 hover:bg-(--color-muted)/60"
            >
              {/*
                Gemini PR #39 review #3 suggested `to="/meetings/$id"
                params={...}` for type safety. Reverted because TanStack
                Router's Link doesn't interpolate $params to a real `href`
                under the test setup (jsdom + ad-hoc router built in
                tests) — the rendered DOM gets `href="/meetings/$id"`
                literal and breaks the e2e-shaped assertion in
                `meeting-links-section.test.tsx (b)`. `meeting-card.tsx`
                uses the same cast workaround for the same reason; once
                the test infra grows a router-context provider that knows
                about typed routes, both call sites can switch.
              */}
              <Link
                {...({
                  to: `/meetings/${link.other_meeting_id}`,
                } as { to: "/meetings/$id"; params: { id: string } })}
                data-testid={`meeting-link-row-${link.link_id}`}
                className="inline-flex flex-1 items-center justify-between gap-2 text-sm text-(--color-foreground) hover:underline"
              >
                <span className="truncate font-medium">{link.other_meeting_title}</span>
                <span className="shrink-0 text-xs text-(--color-muted-foreground)">
                  {_formatScheduledTime(link.other_meeting_scheduled_start_at, i18n.language)}
                </span>
              </Link>
              <button
                type="button"
                onClick={() => deleteMutation.mutate(link.link_id)}
                data-testid={`meeting-link-delete-${link.link_id}`}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-(--color-muted-foreground) transition-colors hover:bg-(--color-destructive)/10 hover:text-(--color-destructive)"
                aria-label={t("meetings.detail.deleteButton")}
              >
                <Trash2 className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {overThreshold && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setExpanded((s) => !s)}
          data-testid="meeting-links-toggle"
          className="self-start text-xs"
        >
          {expanded ? t("meetings.links.showFewer") : t("meetings.links.showMore")}
        </Button>
      )}

      {pickerOpen && (
        <MeetingLinkPicker
          currentMeetingId={meetingId}
          existingLinks={links}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}
