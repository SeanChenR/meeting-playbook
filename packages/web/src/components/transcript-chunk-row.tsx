/**
 * TranscriptChunkRow — slice-16 task 10.5 (rewrite for chunk action menu).
 *
 * Row in the transcript pane. Renders the chunk text + a persistent ✎
 * icon at the trailing edge that opens `<ChunkActionMenu>` on click.
 * The hover-revealed ▶ / ✎ pair from slice-16 v1 is gone; chunk-level
 * actions all live inside the menu now.
 *
 * Inline modes:
 *   - editText: textarea + Save / Cancel (calls PATCH endpoint)
 *   - renameSpeaker: input replacing the speaker name (writes localStorage
 *     via the parent's onRenameCommit callback)
 *
 * Color resolution moved to transcript-pane via _resolveClusterColor; this
 * component is presentation-only for the row body + menu trigger.
 */

import { Pencil } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { localizedErrorMessage } from "../lib/i18n-errors";
import {
  TranscriptEditApiError,
  patchTranscriptChunk,
  type PatchedChunk,
} from "../lib/transcript-edit-api";
import { ChunkActionMenu } from "./chunk-action-menu";

export interface TranscriptChunkRowProps {
  meetingId: string;
  chunkId: string;
  text: string;
  /** Cluster index (1-indexed) when speaker matches /^speaker_cluster_(\d+)$/. */
  clusterN: number | null;
  /** True when the resolved recording is past its 30-day retention window. */
  recordingExpired?: boolean;
  /** Called when the ▶ menu item fires. The parent dispatches to the mini-player. */
  onPlay?: (chunkId: string) => void;
  /** Called when "Edit color" fires; the parent opens `<SpeakerColorPopover>`. */
  onEditColor?: (clusterN: number) => void;
  /** Called after a successful PATCH so the parent can update the cached chunk. */
  onEdited?: (patched: PatchedChunk) => void;
  /** Called when the rename input commits a new label. Empty/over-long values
   *  SHALL have been validated by the parent before this fires. */
  onRenameCommit?: (clusterN: number, label: string) => void;
}

export function TranscriptChunkRow({
  meetingId,
  chunkId,
  text: initialText,
  clusterN,
  recordingExpired = false,
  onPlay,
  onEditColor,
  onEdited,
  onRenameCommit,
}: TranscriptChunkRowProps) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(initialText);
  const [renameDraft, setRenameDraft] = useState("");
  const [text, setText] = useState(initialText);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  function _cancelEdit() {
    setDraft(text);
    setEditing(false);
    setError(null);
  }

  async function _saveEdit() {
    setSaving(true);
    setError(null);
    try {
      const patched = await patchTranscriptChunk(meetingId, chunkId, draft);
      setText(patched.text);
      setEditing(false);
      onEdited?.(patched);
    } catch (e) {
      if (e instanceof TranscriptEditApiError) {
        setError(localizedErrorMessage(e.errorCode, t));
      } else {
        setError(localizedErrorMessage("errors.common.unknown", t));
      }
    } finally {
      setSaving(false);
    }
  }

  function _startRename() {
    if (clusterN === null) return;
    setRenameDraft("");
    setRenaming(true);
  }

  function _commitRename() {
    const trimmed = renameDraft.trim();
    if (clusterN === null || trimmed.length < 1 || trimmed.length > 50) {
      setRenaming(false);
      return;
    }
    onRenameCommit?.(clusterN, trimmed);
    setRenaming(false);
  }

  return (
    <div data-testid="transcript-chunk-row" className="relative">
      {editing ? (
        <div className="space-y-2">
          <textarea
            data-testid="chunk-edit-textarea"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("transcript.chunk.edit.placeholder")}
            disabled={saving}
            rows={Math.max(2, draft.split("\n").length + 1)}
            className="w-full rounded-md border border-(--color-border) bg-(--color-card) px-2 py-1.5 text-sm leading-relaxed focus:border-(--color-primary) focus:outline-none"
          />
          {error ? (
            <p data-testid="chunk-edit-error" className="text-xs text-(--color-destructive)">
              {error}
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              data-testid="chunk-edit-cancel"
              onClick={_cancelEdit}
              disabled={saving}
              className="rounded-md border border-(--color-border) px-2.5 py-1 text-xs text-(--color-muted-foreground) hover:text-(--color-foreground)"
            >
              {t("transcript.chunk.edit.cancel")}
            </button>
            <button
              type="button"
              data-testid="chunk-edit-save"
              onClick={_saveEdit}
              disabled={saving || draft.length === 0 || draft.length > 10_000}
              className="rounded-md border border-(--color-primary) bg-(--color-primary) px-2.5 py-1 text-xs font-medium text-(--color-primary-foreground) hover:bg-(--color-primary)/90 disabled:opacity-50"
            >
              {t("transcript.chunk.edit.save")}
            </button>
          </div>
        </div>
      ) : renaming ? (
        <div className="flex items-center gap-2">
          <input
            data-testid="chunk-rename-input"
            autoFocus
            value={renameDraft}
            onChange={(e) => setRenameDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                _commitRename();
              } else if (e.key === "Escape") {
                e.preventDefault();
                setRenaming(false);
              }
            }}
            placeholder={t("transcript.chunk.rename.placeholder")}
            maxLength={50}
            className="flex-1 rounded-md border border-(--color-border) bg-(--color-card) px-2 py-1 text-sm focus:border-(--color-primary) focus:outline-none"
          />
          <button
            type="button"
            data-testid="chunk-rename-save"
            onClick={_commitRename}
            disabled={renameDraft.trim().length < 1 || renameDraft.trim().length > 50}
            className="rounded-md border border-(--color-primary) bg-(--color-primary) px-2.5 py-1 text-xs font-medium text-(--color-primary-foreground) hover:bg-(--color-primary)/90 disabled:opacity-50"
          >
            {t("transcript.chunk.rename.save")}
          </button>
          <button
            type="button"
            data-testid="chunk-rename-cancel"
            onClick={() => setRenaming(false)}
            className="rounded-md border border-(--color-border) px-2.5 py-1 text-xs text-(--color-muted-foreground)"
          >
            {t("transcript.chunk.rename.cancel")}
          </button>
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <p className="flex-1 whitespace-pre-wrap text-sm leading-relaxed text-(--color-foreground)">
            {text}
          </p>
          <button
            ref={triggerRef}
            type="button"
            data-testid="chunk-action-menu-trigger"
            onClick={() => setMenuOpen((v) => !v)}
            title={t("transcript.chunk.actions.open")}
            aria-label={t("transcript.chunk.actions.open")}
            className="shrink-0 rounded-md border border-(--color-border) p-1 text-(--color-muted-foreground) transition-colors hover:text-(--color-foreground)"
          >
            <Pencil className="size-3.5" aria-hidden />
          </button>
          <ChunkActionMenu
            open={menuOpen}
            onOpenChange={setMenuOpen}
            anchorRef={triggerRef}
            clusterN={clusterN}
            recordingExpired={recordingExpired}
            onPlay={() => onPlay?.(chunkId)}
            onEditText={() => {
              setEditing(true);
              setDraft(text);
            }}
            onEditColor={() => {
              if (clusterN !== null) onEditColor?.(clusterN);
            }}
            onRenameSpeaker={_startRename}
          />
        </div>
      )}
    </div>
  );
}
