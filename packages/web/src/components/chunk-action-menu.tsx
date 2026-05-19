/**
 * ChunkActionMenu — slice-16 task 10.4, rewritten in UI overhaul follow-up.
 *
 * Owns its own ✎ trigger and wraps the menu items in the animate-ui
 * Popover so opening / closing / repositioning all get the framer
 * scale+fade transition for free. The old hand-rolled fixed-position
 * div + manual click-outside + manual Escape handling are retired.
 *
 *   Always:        Play this chunk, Edit text
 *   Cluster only:  Edit color, Rename speaker
 *
 * `me` / `counterparty` / `speaker_cluster_unknown` receive only the
 * first two items.
 */

import { Palette, Pencil, Play, UserPen } from "lucide-react";
import { useCallback, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

export interface ChunkActionMenuProps {
  /** Cluster index when the chunk's speaker matches /^speaker_cluster_(\d+)$/. */
  clusterN: number | null;
  /** True when the resolved recording is past its 30-day retention window. */
  recordingExpired: boolean;
  onPlay: () => void;
  onEditText: () => void;
  onEditColor: () => void;
  onRenameSpeaker: () => void;
}

export function ChunkActionMenu({
  clusterN,
  recordingExpired,
  onPlay,
  onEditText,
  onEditColor,
  onRenameSpeaker,
}: ChunkActionMenuProps): ReactNode {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const select = useCallback(
    (cb: () => void) => () => {
      cb();
      setOpen(false);
    },
    [],
  );

  const isCluster = clusterN !== null && Number.isFinite(clusterN);
  const playLabel = recordingExpired
    ? t("meeting.detail.audioPlayer.chunkExpired")
    : t("transcript.chunk.actions.play");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="chunk-action-menu-trigger"
          title={t("transcript.chunk.actions.open")}
          aria-label={t("transcript.chunk.actions.open")}
          className="shrink-0 rounded-md border border-(--color-border) p-1 text-(--color-muted-foreground) transition-colors hover:text-(--color-foreground) hover:border-(--color-primary)/40"
        >
          <Pencil className="size-3.5" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={6}
        data-testid="chunk-action-menu"
        role="menu"
        aria-label={t("transcript.chunk.actions.open")}
        className="w-44 p-1"
      >
        <button
          type="button"
          role="menuitem"
          data-testid="chunk-action-play"
          disabled={recordingExpired}
          onClick={select(onPlay)}
          aria-label={playLabel}
          title={playLabel}
          className={cn(
            "flex w-full items-center gap-2 rounded-(--radius-sm) px-3 py-1.5 text-left text-xs text-(--color-foreground)",
            "hover:bg-(--color-primary)/10 disabled:cursor-not-allowed disabled:opacity-40",
          )}
        >
          <Play className="size-3.5" aria-hidden />
          {t("transcript.chunk.actions.play")}
        </button>

        <button
          type="button"
          role="menuitem"
          data-testid="chunk-action-edit-text"
          onClick={select(onEditText)}
          className="flex w-full items-center gap-2 rounded-(--radius-sm) px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
        >
          <Pencil className="size-3.5" aria-hidden />
          {t("transcript.chunk.actions.editText")}
        </button>

        {isCluster && (
          <button
            type="button"
            role="menuitem"
            data-testid="chunk-action-edit-color"
            onClick={select(onEditColor)}
            className="flex w-full items-center gap-2 rounded-(--radius-sm) px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
          >
            <Palette className="size-3.5" aria-hidden />
            {t("transcript.chunk.actions.editColor")}
          </button>
        )}

        {isCluster && (
          <button
            type="button"
            role="menuitem"
            data-testid="chunk-action-rename"
            onClick={select(onRenameSpeaker)}
            className="flex w-full items-center gap-2 rounded-(--radius-sm) px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
          >
            <UserPen className="size-3.5" aria-hidden />
            {t("transcript.chunk.actions.renameSpeaker")}
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}
