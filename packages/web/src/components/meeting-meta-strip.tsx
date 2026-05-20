/**
 * MeetingMetaStrip — visible affordances row between header bar and tabs.
 *
 * Surfaces three menu items (tags / attachments / linked) inline so the page
 * isn't dependent on the ⋯ menu to discover them. Items remain in the menu
 * too — this strip is an additional, lighter entry point.
 */

import { Link2, Paperclip, Plus, Tag as TagIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { MeetingTagSummary } from "../lib/meetings-api";
import { TagChip } from "./tags/tag-chip";

export interface MeetingMetaStripProps {
  tags: MeetingTagSummary[];
  attachmentsCount: number;
  linksCount: number;
  onTagsOpen: () => void;
  onAttachmentsOpen: () => void;
  onLinkedOpen: () => void;
}

function _CountChip({
  icon,
  label,
  count,
  onClick,
  testId,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="inline-flex items-center gap-1.5 rounded-full border border-(--color-border) bg-(--color-surface) px-3 py-1 text-[12px] text-(--color-muted-foreground) transition-colors hover:border-(--color-border-strong) hover:bg-(--color-surface-2) hover:text-(--color-foreground)"
    >
      {icon}
      <span>{label}</span>
      {count > 0 && (
        <span className="ml-0.5 inline-flex items-center justify-center rounded-full bg-(--color-primary-soft) px-1.5 text-[11px] font-medium text-(--color-primary)">
          {count}
        </span>
      )}
    </button>
  );
}

export function MeetingMetaStrip({
  tags,
  attachmentsCount,
  linksCount,
  onTagsOpen,
  onAttachmentsOpen,
  onLinkedOpen,
}: MeetingMetaStripProps) {
  const { t } = useTranslation();

  return (
    <div data-testid="meeting-meta-strip" className="flex flex-wrap items-center gap-2 py-1">
      {/* Tag chips */}
      {tags.length > 0 &&
        tags.map((tag) => <TagChip key={tag.id} name={tag.name} color={tag.color} />)}
      <button
        type="button"
        onClick={onTagsOpen}
        data-testid="meta-strip-tags"
        className="inline-flex items-center gap-1 rounded-full border border-dashed border-(--color-border) bg-transparent px-2.5 py-0.5 text-[11px] text-(--color-muted-foreground) hover:border-(--color-border-strong) hover:text-(--color-foreground)"
      >
        {tags.length === 0 ? (
          <>
            <TagIcon className="size-3" strokeWidth={1.5} aria-hidden />
            <span>{t("meetings.detail.menu.tags")}</span>
          </>
        ) : (
          <>
            <Plus className="size-3" strokeWidth={1.5} aria-hidden />
            <span>{t("meetings.detail.menu.tags")}</span>
          </>
        )}
      </button>

      <span aria-hidden className="mx-1 h-3.5 w-px bg-(--color-border)" />

      <_CountChip
        icon={<Paperclip className="size-3.5" strokeWidth={1.5} aria-hidden />}
        label={t("meetings.detail.menu.attachments")}
        count={attachmentsCount}
        onClick={onAttachmentsOpen}
        testId="meta-strip-attachments"
      />

      <_CountChip
        icon={<Link2 className="size-3.5" strokeWidth={1.5} aria-hidden />}
        label={t("meetings.detail.menu.linked")}
        count={linksCount}
        onClick={onLinkedOpen}
        testId="meta-strip-linked"
      />
    </div>
  );
}
