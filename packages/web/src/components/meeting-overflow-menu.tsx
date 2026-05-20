/**
 * MeetingOverflowMenu — 8-item dropdown opened by ⋯ MoreHorizontal trigger.
 *
 * Items (in document order, with two separators):
 *   1. 編輯會議       [Pencil]
 *   2. 管理標籤       [Tag]
 *   3. 附件 (N)       [Paperclip]   ← count badge
 *   4. 相關會議 (N)    [Link2]       ← count badge
 *   ──────────────────────────────
 *   5. 錄音模式       [Mic2]   ← conditional (scheduled + idle), shows current mode sub-hint
 *   6. 重跑轉錄       [RotateCw]
 *   ──────────────────────────────
 *   7. 刪除會議       [Trash2]  ← destructive
 *
 * ASR Provider deliberately NOT here — moved to /settings/integrations
 * (Decision 12). Only 8 items total (or 7 when mode hidden).
 */

import {
  ChevronRight,
  Link2,
  Mic2,
  MoreHorizontal,
  Paperclip,
  Pencil,
  RotateCw,
  Settings2,
  Tag,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

export interface MeetingOverflowMenuProps {
  /** Number of attached files (badge). 0 → no badge. */
  attachmentsCount: number;
  /** Number of linked meetings (badge). 0 → no badge. */
  linksCount: number;
  /** Current ASR provider display label (e.g. "Whisper Large v3"). */
  asrCurrentLabel?: string;
  /** Current recording mode display label (e.g. 雙路 ASR). Drives `mode` sub-hint. */
  modeCurrentLabel?: string;
  /** When false, `mode` item is hidden (only visible if scheduled+idle). */
  showModeItem: boolean;
  onEdit: () => void;
  onTagsOpen: () => void;
  onAttachmentsOpen: () => void;
  onLinkedOpen: () => void;
  onAsrOpen: () => void;
  onModeOpen: () => void;
  onRerun: () => void;
  onDelete: () => void;
}

function _CountBadge({ n }: { n: number }) {
  if (n <= 0) return null;
  return (
    <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-(--color-primary-soft) px-1.5 text-xs font-medium text-(--color-primary)">
      {n}
    </span>
  );
}

export function MeetingOverflowMenu({
  attachmentsCount,
  linksCount,
  asrCurrentLabel,
  modeCurrentLabel,
  showModeItem,
  onEdit,
  onTagsOpen,
  onAttachmentsOpen,
  onLinkedOpen,
  onAsrOpen,
  onModeOpen,
  onRerun,
  onDelete,
}: MeetingOverflowMenuProps) {
  const { t } = useTranslation();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          data-testid="meeting-overflow-trigger"
          aria-label="更多"
        >
          <MoreHorizontal className="size-4" strokeWidth={1.5} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[200px]">
        {/* Group 1 — Data */}
        <DropdownMenuItem data-testid="meeting-menu-item-edit" onSelect={onEdit}>
          <Pencil className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.edit")}
        </DropdownMenuItem>
        <DropdownMenuItem data-testid="meeting-menu-item-tags" onSelect={onTagsOpen}>
          <Tag className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.tags")}
        </DropdownMenuItem>
        <DropdownMenuItem data-testid="meeting-menu-item-attachments" onSelect={onAttachmentsOpen}>
          <Paperclip className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.attachments")}
          <_CountBadge n={attachmentsCount} />
        </DropdownMenuItem>
        <DropdownMenuItem data-testid="meeting-menu-item-linked" onSelect={onLinkedOpen}>
          <Link2 className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.linked")}
          <_CountBadge n={linksCount} />
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Group 2 — Settings (ASR Provider returns per Claude Design v2) */}
        <DropdownMenuItem data-testid="meeting-menu-item-asr" onSelect={onAsrOpen}>
          <Settings2 className="size-4" strokeWidth={1.5} />
          <span>ASR 引擎</span>
          {asrCurrentLabel && (
            <span className="ml-auto inline-flex items-center gap-1 text-xs text-(--color-muted-foreground)">
              {asrCurrentLabel}
              <ChevronRight className="size-3" strokeWidth={1.5} />
            </span>
          )}
        </DropdownMenuItem>
        {showModeItem && (
          <DropdownMenuItem data-testid="meeting-menu-item-mode" onSelect={onModeOpen}>
            <Mic2 className="size-4" strokeWidth={1.5} />
            {t("meetings.detail.menu.mode")}
            {modeCurrentLabel && (
              <span className="ml-2 text-xs text-(--color-muted-foreground)">
                {modeCurrentLabel}
              </span>
            )}
          </DropdownMenuItem>
        )}
        <DropdownMenuItem data-testid="meeting-menu-item-rerun" onSelect={onRerun}>
          <RotateCw className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.rerun")}
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Group 3 — Destructive */}
        <DropdownMenuItem
          data-testid="meeting-menu-item-delete"
          onSelect={onDelete}
          className="text-(--color-destructive) focus:text-(--color-destructive) focus:bg-(--color-destructive)/10"
        >
          <Trash2 className="size-4" strokeWidth={1.5} />
          {t("meetings.detail.menu.delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
