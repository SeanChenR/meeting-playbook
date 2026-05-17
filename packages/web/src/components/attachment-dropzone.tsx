/**
 * AttachmentDropzone — slice-20a task 5.2.
 *
 * Surfaces the four meeting-attachment endpoints in a single composable
 * widget. The four API helpers are wired via the `api` prop so tests can
 * inject mocks without monkey-patching `fetch` / `XMLHttpRequest`. The
 * component:
 *   - lists existing attachments (with per-row download + delete)
 *   - exposes a drag-drop zone + click-to-pick file input
 *   - renders a progress card while an upload is in flight
 *   - renders a localized error (via `localizedErrorMessage`) on failure;
 *     existing rows survive across failed upload attempts
 *
 * The `api` prop default is the real `attachments-api.ts` module so the
 * production caller does not have to pass anything.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type Attachment,
  AttachmentApiError,
  deleteAttachment as _deleteAttachment,
  getDownloadUrl as _getDownloadUrl,
  listAttachments as _listAttachments,
  uploadAttachment as _uploadAttachment,
} from "../lib/attachments-api";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { Alert } from "./ui/alert";
import { buttonVariants } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export interface AttachmentDropzoneApi {
  listAttachments: (meetingId: string) => Promise<Attachment[]>;
  uploadAttachment: (
    meetingId: string,
    file: File,
    onProgress?: (percent: number) => void,
  ) => Promise<Attachment>;
  deleteAttachment: (meetingId: string, attachmentId: string) => Promise<void>;
  getDownloadUrl: (meetingId: string, attachmentId: string) => string;
}

const _DEFAULT_API: AttachmentDropzoneApi = {
  listAttachments: _listAttachments,
  uploadAttachment: _uploadAttachment,
  deleteAttachment: _deleteAttachment,
  getDownloadUrl: _getDownloadUrl,
};

export interface AttachmentDropzoneProps {
  meetingId: string;
  api?: AttachmentDropzoneApi;
}

function _formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentDropzone({ meetingId, api = _DEFAULT_API }: AttachmentDropzoneProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [progress, setProgress] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const listQuery = useQuery({
    queryKey: ["meeting-attachments", meetingId],
    queryFn: () => api.listAttachments(meetingId),
  });

  // The playbook + summary expose `is_stale` derived from the live
  // attachment-set hash vs the snapshot at last generation. Whenever the
  // attachment list changes the server-side flag would flip, but the
  // client doesn't know until it refetches. Invalidating both queries on
  // upload / delete keeps the stale banners in sync without a page
  // refresh.
  function _refreshGeneratedArtifacts() {
    queryClient.invalidateQueries({ queryKey: ["playbook", meetingId] });
    queryClient.invalidateQueries({ queryKey: ["summary", meetingId] });
  }

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      api.uploadAttachment(meetingId, file, (percent) => setProgress(percent)),
    onSuccess: (newRow) => {
      queryClient.setQueryData<Attachment[]>(["meeting-attachments", meetingId], (prev) => {
        return prev ? [newRow, ...prev] : [newRow];
      });
      _refreshGeneratedArtifacts();
      setProgress(null);
      setErrorMessage(null);
    },
    onError: (err) => {
      const code = err instanceof AttachmentApiError ? err.errorCode : undefined;
      setErrorMessage(code ? localizedErrorMessage(code, t) : t("errors.common.unknown"));
      setProgress(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (attachmentId: string) => api.deleteAttachment(meetingId, attachmentId),
    onSuccess: (_data, attachmentId) => {
      queryClient.setQueryData<Attachment[]>(["meeting-attachments", meetingId], (prev) => {
        return prev?.filter((row) => row.id !== attachmentId) ?? [];
      });
      _refreshGeneratedArtifacts();
    },
    onError: (err) => {
      const code = err instanceof AttachmentApiError ? err.errorCode : undefined;
      setErrorMessage(code ? localizedErrorMessage(code, t) : t("errors.common.unknown"));
    },
  });

  const rows = listQuery.data ?? [];

  function _handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!file) return;
    setErrorMessage(null);
    uploadMutation.mutate(file);
  }

  function _handleDelete(attachmentId: string) {
    if (!window.confirm(t("attachments.deleteConfirm"))) return;
    deleteMutation.mutate(attachmentId);
  }

  return (
    <div data-testid="attachment-dropzone" className="space-y-3">
      <p className="text-xs text-(--color-muted-foreground)">{t("attachments.hintLimit")}</p>

      <Card>
        <CardContent
          data-testid="attachment-dropzone-area"
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            _handleFiles(e.dataTransfer.files);
          }}
          className={
            dragOver
              ? "flex flex-col items-center justify-center gap-2 border-2 border-dashed border-(--color-primary) bg-(--color-primary)/5 p-6 text-center"
              : "flex flex-col items-center justify-center gap-2 border-2 border-dashed border-(--color-border) p-6 text-center"
          }
        >
          <p className="text-sm text-(--color-muted-foreground)">
            {t("attachments.dropzoneLabel")}
          </p>
          <input
            ref={inputRef}
            type="file"
            data-testid="attachment-file-input"
            className="sr-only"
            onChange={(e) => _handleFiles(e.target.files)}
          />
          <button
            type="button"
            data-testid="attachment-upload-button"
            onClick={() => inputRef.current?.click()}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            {t("attachments.uploadButton")}
          </button>
        </CardContent>
      </Card>

      {progress !== null && (
        <Card data-testid="attachment-progress-card">
          <CardContent className="space-y-1.5 p-3">
            <p className="text-xs text-(--color-muted-foreground)">
              {t("attachments.uploadingLabel", { percent: progress })}
            </p>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-(--color-muted)">
              <div
                data-testid="attachment-progress-bar"
                className="h-full bg-(--color-primary) transition-[width]"
                style={{ width: `${progress}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {errorMessage && (
        <Alert data-testid="attachment-error" variant="destructive">
          {errorMessage}
        </Alert>
      )}

      {rows.length === 0 ? (
        <p
          data-testid="attachment-empty-state"
          className="rounded-md border border-(--color-border) px-3 py-4 text-center text-sm text-(--color-muted-foreground)"
        >
          {t("attachments.emptyState")}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map((row) => (
            <li
              key={row.id}
              data-testid="attachment-row"
              data-attachment-id={row.id}
              className="flex flex-wrap items-center gap-2 rounded-md border border-(--color-border) px-3 py-2 text-sm"
            >
              <span className="flex-1 truncate font-medium text-(--color-foreground)">
                {row.original_name}
              </span>
              <span className="text-xs text-(--color-muted-foreground)">
                {t(`attachments.kind.${row.kind}`)} · {_formatBytes(row.bytes)}
              </span>
              <a
                href={api.getDownloadUrl(meetingId, row.id)}
                download={row.original_name}
                data-testid={`attachment-download-${row.id}`}
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                {t("attachments.downloadButton")}
              </a>
              <button
                type="button"
                data-testid={`attachment-delete-${row.id}`}
                onClick={() => _handleDelete(row.id)}
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                {t("attachments.deleteButton")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
