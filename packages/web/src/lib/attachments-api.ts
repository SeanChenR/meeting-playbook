/**
 * Meeting-attachment REST client.
 *
 * Wraps the 4 endpoints under `/api/meetings/{id}/attachments` (slice-20a):
 *   - `listAttachments(meetingId)` → GET, returns `Attachment[]`
 *   - `uploadAttachment(meetingId, file, onProgress)` → POST via XHR so the
 *     dropzone can render a 0-100 progress bar. The dropzone subscribes
 *     to `onProgress` and the helper resolves to the new row on 200,
 *     rejects with `AttachmentApiError` on any non-2xx.
 *   - `deleteAttachment(meetingId, attachmentId)` → DELETE
 *   - `getDownloadUrl(meetingId, attachmentId)` → relative URL (no fetch)
 *
 * Plus a slice-20b stub for the meeting-create preview form:
 *   - `listPendingAttachments()` → GET `/api/attachments?status=pending`,
 *     returns `[]` on any non-2xx (graceful degradation while the backend
 *     endpoint is still missing).
 *
 * Error shape mirrors `meetings-api.ts` — backend `{error_code, message}`
 * envelopes become an `AttachmentApiError` carrying `errorCode` that the
 * UI passes to `localizedErrorMessage(t)`.
 */

export type AttachmentKind = "image" | "pdf" | "docx" | "text" | "markdown";

export interface Attachment {
  id: string;
  kind: AttachmentKind;
  original_name: string;
  bytes: number;
  uploaded_at: string;
}

export interface ListAttachmentsResponse {
  attachments: Attachment[];
}

export class AttachmentApiError extends Error {
  readonly status: number;
  readonly errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.name = "AttachmentApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<AttachmentApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // non-JSON body — keep defaults
  }
  return new AttachmentApiError(
    resp.status,
    body.error_code,
    body.message ?? `HTTP ${resp.status}`,
  );
}

export async function listAttachments(meetingId: string): Promise<Attachment[]> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/attachments`);
  if (!resp.ok) throw await _envelopeError(resp);
  const body = (await resp.json()) as ListAttachmentsResponse;
  return body.attachments;
}

/**
 * Upload a file via XHR so the caller receives per-chunk progress.
 *
 * `onProgress` is called with a percent value in [0, 100]. It is invoked
 * at least once with `0` immediately so the UI can mount the progress
 * card before the first byte goes out the door (matches the spec
 * scenario "progress card transitioning from 0% to 100%").
 *
 * Rejects with `AttachmentApiError` on any non-2xx response so the
 * dropzone can localize via `localizedErrorMessage(err.errorCode, t)`.
 */
export function uploadAttachment(
  meetingId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Attachment> {
  return new Promise<Attachment>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/meetings/${encodeURIComponent(meetingId)}/attachments`, true);

    // Fire 0% immediately so the UI can render a progress card before the
    // first network event arrives. Some browsers fire the first onprogress
    // only after the first ack — without this seed the progress card would
    // flash empty.
    if (onProgress) {
      try {
        onProgress(0);
      } catch {
        // Ignore caller errors — we don't want the upload to fail because
        // the UI callback threw.
      }
    }

    xhr.upload.onprogress = (evt) => {
      if (!onProgress || !evt.lengthComputable) return;
      const percent = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
      try {
        onProgress(percent);
      } catch {
        // see above
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const att = JSON.parse(xhr.responseText) as Attachment;
          resolve(att);
        } catch (err) {
          reject(
            new AttachmentApiError(
              xhr.status,
              "common.internal_error",
              `Malformed JSON in success response: ${(err as Error).message}`,
            ),
          );
        }
        return;
      }
      let errorCode: string | undefined;
      let message = `HTTP ${xhr.status}`;
      try {
        const body = JSON.parse(xhr.responseText) as {
          error_code?: string;
          message?: string;
        };
        if (typeof body.error_code === "string") errorCode = body.error_code;
        if (typeof body.message === "string" && body.message.length > 0) {
          message = body.message;
        }
      } catch {
        // ignore — leave defaults
      }
      reject(new AttachmentApiError(xhr.status, errorCode, message));
    };

    xhr.onerror = () => {
      reject(new AttachmentApiError(0, "common.network_error", "Network error"));
    };

    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}

export async function deleteAttachment(meetingId: string, attachmentId: string): Promise<void> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/attachments/${encodeURIComponent(attachmentId)}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw await _envelopeError(resp);
}

/**
 * Compose the download URL for the given attachment. No network call.
 *
 * The frontend uses `<a href>` to trigger the browser's native download
 * UI, which honours `Content-Disposition: attachment` from the backend
 * and preserves the original filename.
 */
export function getDownloadUrl(meetingId: string, attachmentId: string): string {
  return `/api/meetings/${encodeURIComponent(meetingId)}/attachments/${encodeURIComponent(attachmentId)}/download`;
}

// ─── slice-20b: pending-attachment picker for the meeting preview form ───

/**
 * A user-uploaded staged attachment (`meeting_id IS NULL`). The
 * `<StagedAttachmentDropzone>` on `/meetings/new` lists these so users
 * can drop files now and have them attached when the meeting is created.
 *
 * Slice-24 extends the shape from the slice-20b stub (just `id` +
 * optional `filename`) to the full Attachment shape so the dropzone can
 * render file size + kind without a second round-trip.
 */
export interface PendingAttachment {
  id: string;
  // The dropzone displays `original_name` when present; `filename` is
  // the legacy slice-20b alias kept for backward compatibility with
  // tests that still set `filename` on stub data.
  original_name?: string;
  filename?: string;
  kind?: AttachmentKind;
  bytes?: number;
  uploaded_at?: string;
}

interface PendingAttachmentsResponse {
  attachments: PendingAttachment[];
}

/**
 * Fetches the current user's pending (unattached) attachments.
 *
 * Slice-24: the endpoint now exists for real (`GET /api/attachments?
 * status=pending` returns `{attachments: [...]}` per the staging spec).
 * The slice-20b graceful fallback is preserved — a non-2xx response or
 * a network error returns `[]` so the dropzone never blocks rendering.
 */
export async function listPendingAttachments(): Promise<PendingAttachment[]> {
  try {
    const resp = await fetch("/api/attachments?status=pending");
    if (!resp.ok) {
      // Graceful degradation — see function doc.
      return [];
    }
    const body = (await resp.json()) as PendingAttachmentsResponse | PendingAttachment[];
    if (Array.isArray(body)) {
      // Legacy stub shape — slice-20b returned a bare array.
      return body;
    }
    return Array.isArray(body.attachments) ? body.attachments : [];
  } catch {
    return [];
  }
}

export function pendingAttachmentsQueryOptions() {
  return {
    queryKey: ["attachments", "pending"] as const,
    queryFn: listPendingAttachments,
    // Don't retry — the empty fallback already covers the missing-endpoint
    // case, and stale data here is harmless.
    retry: false,
  };
}

/**
 * Slice-24: upload a file to the per-user staging area.
 *
 * POSTs to `/api/attachments/staging` via XHR so the dropzone can render
 * per-file progress, mirroring the meeting-scoped `uploadAttachment`
 * helper. On success the row carries `meeting_id=NULL`; the dropzone
 * keeps the id in its `selectedIds[]` so submitting the form attaches
 * it to the new meeting.
 */
export function uploadStagedAttachment(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Attachment> {
  return new Promise<Attachment>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/attachments/staging", true);

    if (onProgress) {
      try {
        onProgress(0);
      } catch {
        // Ignore caller errors — same defensive pattern as the
        // meeting-scoped upload helper.
      }
    }

    xhr.upload.onprogress = (evt) => {
      if (!onProgress || !evt.lengthComputable) return;
      const percent = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
      try {
        onProgress(percent);
      } catch {
        // see above
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const att = JSON.parse(xhr.responseText) as Attachment;
          resolve(att);
        } catch (err) {
          reject(
            new AttachmentApiError(
              xhr.status,
              "common.internal_error",
              `Malformed JSON in success response: ${(err as Error).message}`,
            ),
          );
        }
        return;
      }
      let errorCode: string | undefined;
      let message = `HTTP ${xhr.status}`;
      try {
        const body = JSON.parse(xhr.responseText) as {
          error_code?: string;
          message?: string;
        };
        if (typeof body.error_code === "string") errorCode = body.error_code;
        if (typeof body.message === "string" && body.message.length > 0) {
          message = body.message;
        }
      } catch {
        // ignore — leave defaults
      }
      reject(new AttachmentApiError(xhr.status, errorCode, message));
    };

    xhr.onerror = () => {
      reject(new AttachmentApiError(0, "common.network_error", "Network error"));
    };

    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}

/**
 * Slice-24: delete a staged attachment by id.
 *
 * Routes to `/api/attachments/{id}` (top-level, no meeting id in the
 * path). The backend refuses to delete attached rows here — callers
 * with an attached attachment must use the meeting-scoped delete.
 */
export async function deleteStagedAttachment(attachmentId: string): Promise<void> {
  const resp = await fetch(`/api/attachments/${encodeURIComponent(attachmentId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw await _envelopeError(resp);
}
