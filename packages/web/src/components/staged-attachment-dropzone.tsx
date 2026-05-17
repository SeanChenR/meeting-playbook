/**
 * StagedAttachmentDropzone — slice-24 task 7.1.
 *
 * Per spec meeting-attachment ADDED requirement
 * "Frontend StagedAttachmentDropzone uploads to staging and lists current
 * staged":
 *
 *   - Drag-drop / click-to-pick zone wired to POST /api/attachments/staging
 *   - Lists current staged attachments with a per-row remove button (the
 *     ✕ calls DELETE /api/attachments/{id})
 *   - Per-file upload progress while a POST is in flight
 *   - Backend error codes localized through `localizedErrorMessage`
 *
 * The parent (`/meetings/new`) holds the form-side `selectedIds[]` state;
 * the dropzone syncs it via `onChange` whenever the staged list changes
 * — so on submit the form just sends `selectedIds` as `attachments[]`.
 *
 * This component is intentionally distinct from `<AttachmentDropzone>`
 * (slice-20a, meeting-detail page) because:
 *  - the API URLs differ (meeting-scoped vs user-scoped),
 *  - cache invalidation targets differ (per-meeting query vs the global
 *    `["attachments", "pending"]` query),
 *  - the dropzone has no download / kind preview affordances since
 *    staged rows aren't shareable yet.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type Attachment,
  AttachmentApiError,
  type PendingAttachment,
  deleteStagedAttachment as _deleteStagedAttachment,
  listPendingAttachments as _listPendingAttachments,
  pendingAttachmentsQueryOptions,
  uploadStagedAttachment as _uploadStagedAttachment,
} from "../lib/attachments-api";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { Alert } from "./ui/alert";
import { buttonVariants } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export interface StagedAttachmentDropzoneApi {
  listPendingAttachments: () => Promise<PendingAttachment[]>;
  uploadStagedAttachment: (
    file: File,
    onProgress?: (percent: number) => void,
  ) => Promise<Attachment>;
  deleteStagedAttachment: (attachmentId: string) => Promise<void>;
}

const _DEFAULT_API: StagedAttachmentDropzoneApi = {
  listPendingAttachments: _listPendingAttachments,
  uploadStagedAttachment: _uploadStagedAttachment,
  deleteStagedAttachment: _deleteStagedAttachment,
};

export interface StagedAttachmentDropzoneProps {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  api?: StagedAttachmentDropzoneApi;
}

function _formatBytes(bytes: number | undefined): string {
  if (bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function StagedAttachmentDropzone({
  selectedIds,
  onChange,
  api = _DEFAULT_API,
}: StagedAttachmentDropzoneProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [progress, setProgress] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const listQuery = useQuery({
    ...pendingAttachmentsQueryOptions(),
    queryFn: api.listPendingAttachments,
  });

  const rows: PendingAttachment[] = listQuery.data ?? [];

  // Per design D9: `/meetings/new` submit sends every staged row's id.
  // Sync `selectedIds` to the live staged list — any drift (e.g. an
  // upload that resolved after the parent rendered) self-heals on
  // next render.
  useEffect(() => {
    const liveIds = rows.map((r) => r.id);
    const selectedSorted = [...selectedIds].sort().join(",");
    const liveSorted = [...liveIds].sort().join(",");
    if (selectedSorted !== liveSorted) {
      onChange(liveIds);
    }
    // We intentionally do not include `onChange` in deps — the parent's
    // setter reference is stable, including it would trip the effect on
    // every render. The selectedIds string-comparison guard is the
    // canonical equality check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadStagedAttachment(file, (percent) => setProgress(percent)),
    onSuccess: (newRow) => {
      // Splice the new row into the cached list so the parent sees it
      // immediately; the effect above will sync selectedIds.
      queryClient.setQueryData<PendingAttachment[]>(["attachments", "pending"], (prev) => {
        const next: PendingAttachment = {
          id: newRow.id,
          kind: newRow.kind,
          original_name: newRow.original_name,
          bytes: newRow.bytes,
          uploaded_at: newRow.uploaded_at,
        };
        return prev ? [...prev, next] : [next];
      });
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
    mutationFn: (attachmentId: string) => api.deleteStagedAttachment(attachmentId),
    onSuccess: (_data, attachmentId) => {
      queryClient.setQueryData<PendingAttachment[]>(["attachments", "pending"], (prev) => {
        return prev?.filter((r) => r.id !== attachmentId) ?? [];
      });
    },
    onError: (err) => {
      const code = err instanceof AttachmentApiError ? err.errorCode : undefined;
      setErrorMessage(code ? localizedErrorMessage(code, t) : t("errors.common.unknown"));
    },
  });

  function _handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!file) return;
    setErrorMessage(null);
    uploadMutation.mutate(file);
  }

  return (
    <div data-testid="staged-dropzone" className="space-y-3">
      {/* Existing staged rows + uploading-progress card */}
      {rows.length > 0 && (
        <ul className="space-y-1.5">
          {rows.map((row) => (
            <li
              key={row.id}
              data-testid={`staged-row-${row.id}`}
              className="flex flex-wrap items-center gap-2 rounded-md border border-(--color-border) px-3 py-2 text-sm"
            >
              <span className="flex-1 truncate font-medium text-(--color-foreground)">
                {row.original_name ?? row.filename ?? row.id}
              </span>
              <span className="text-xs text-(--color-muted-foreground)">
                {_formatBytes(row.bytes)}
              </span>
              <button
                type="button"
                data-testid={`staged-remove-${row.id}`}
                onClick={() => deleteMutation.mutate(row.id)}
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                {t("meetings.new.staging.remove_button")}
              </button>
            </li>
          ))}
        </ul>
      )}

      {progress !== null && (
        <Card data-testid="staged-progress-card">
          <CardContent className="space-y-1.5 p-3">
            <p className="text-xs text-(--color-muted-foreground)">
              {t("meetings.new.staging.uploading_label", { percent: progress })}
            </p>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-(--color-muted)">
              <div
                data-testid="staged-progress-bar"
                className="h-full bg-(--color-primary) transition-[width]"
                style={{ width: `${progress}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {errorMessage && (
        <Alert data-testid="staged-error" variant="destructive">
          {errorMessage}
        </Alert>
      )}

      {/* Dropzone always renders, regardless of whether staged rows exist */}
      <Card>
        <CardContent
          data-testid="staged-dropzone-area"
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
            {rows.length === 0
              ? t("meetings.new.staging.empty_hint")
              : t("meetings.new.staging.dropzone_label")}
          </p>
          <input
            ref={inputRef}
            type="file"
            data-testid="staged-file-input"
            className="sr-only"
            onChange={(e) => _handleFiles(e.target.files)}
          />
          <button
            type="button"
            data-testid="staged-upload-button"
            onClick={() => inputRef.current?.click()}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            {t("meetings.new.staging.dropzone_label")}
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
