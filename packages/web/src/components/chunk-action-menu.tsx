/**
 * ChunkActionMenu — slice-16 task 10.4.
 *
 * Dropdown menu anchored to the persistent ✎ icon at the end of each
 * `<TranscriptChunkRow>`. Replaces the slice-16 v1 hover-revealed
 * ▶/✎ pair and the right-click `<SpeakerColorPopover>` trigger.
 *
 *   Always:        Play this chunk, Edit text
 *   Cluster only:  Edit color, Rename speaker
 *
 * `me` / `counterparty` / `speaker_cluster_unknown` receive only the
 * first two items; the cluster-specific items are DOM-absent so the
 * spec's tooltip / a11y assertions stay clean.
 */

import { Palette, Pencil, Play, UserPen } from "lucide-react";
import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";

export interface ChunkActionMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Anchor element (typically the ✎ icon button); used for positioning. */
  anchorRef?: React.RefObject<HTMLElement | null>;
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
  open,
  onOpenChange,
  anchorRef,
  clusterN,
  recordingExpired,
  onPlay,
  onEditText,
  onEditColor,
  onRenameSpeaker,
}: ChunkActionMenuProps): ReactNode {
  const { t } = useTranslation();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onOpenChange(false);
    }
    function onClickOutside(e: MouseEvent) {
      if (!menuRef.current) return;
      if (menuRef.current.contains(e.target as Node)) return;
      if (anchorRef?.current && anchorRef.current.contains(e.target as Node)) return;
      onOpenChange(false);
    }
    document.addEventListener("keydown", onKeyDown);
    const timer = window.setTimeout(() => {
      document.addEventListener("mousedown", onClickOutside);
    }, 0);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onClickOutside);
      window.clearTimeout(timer);
    };
  }, [open, onOpenChange, anchorRef]);

  const select = useCallback(
    (cb: () => void) => () => {
      cb();
      onOpenChange(false);
    },
    [onOpenChange],
  );

  if (!open) return null;

  const isCluster = clusterN !== null && Number.isFinite(clusterN);
  const playLabel = recordingExpired
    ? t("meeting.detail.audioPlayer.chunkExpired")
    : t("transcript.chunk.actions.play");

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label={t("transcript.chunk.actions.open")}
      data-testid="chunk-action-menu"
      className="fixed z-50 w-44 rounded-lg border border-(--color-border) bg-(--color-card) py-1 shadow-lg"
      style={
        anchorRef?.current
          ? _anchorPosition(anchorRef.current)
          : { top: "50%", left: "50%", transform: "translate(-50%, -50%)" }
      }
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
          "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-(--color-foreground)",
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
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
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
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
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
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-(--color-foreground) hover:bg-(--color-primary)/10"
        >
          <UserPen className="size-3.5" aria-hidden />
          {t("transcript.chunk.actions.renameSpeaker")}
        </button>
      )}
    </div>
  );
}

function _anchorPosition(anchor: HTMLElement): { top: number; left: number } {
  const rect = anchor.getBoundingClientRect();
  return { top: rect.bottom + 4, left: rect.left };
}
