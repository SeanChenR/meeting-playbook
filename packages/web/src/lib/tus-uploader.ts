/**
 * tus-js-client wrapper for offline-ingest uploads (slice-14 task 5.1).
 *
 * Centralises the tus 1.0 POST creation + PATCH chunk loop behind a
 * minimal callback-based API. Direct consumers (`<OfflineIngestUploadDialog>`)
 * pass a `File` + `actualStartedAt` and receive progress / success /
 * failure callbacks; tus-js-client owns the resumable PATCH plumbing.
 *
 * The wrapper is deliberately thin so unit tests can stub the underlying
 * `tus.Upload` class via Vitest's module mock + still exercise our
 * metadata encoding + error mapping.
 */

import * as tus from "tus-js-client";

export class OfflineIngestUploadError extends Error {
  readonly errorCode: string;
  readonly statusCode: number;

  constructor(errorCode: string, message: string, statusCode: number) {
    super(message);
    this.name = "OfflineIngestUploadError";
    this.errorCode = errorCode;
    this.statusCode = statusCode;
  }
}

export interface UploadProgress {
  bytesUploaded: number;
  bytesTotal: number;
}

export interface UploadOfflineAudioOptions {
  meetingId: string;
  file: File;
  actualStartedAt: Date;
  onProgress?: (progress: UploadProgress) => void;
  onComplete?: () => void;
  onError?: (error: OfflineIngestUploadError) => void;
}

export interface UploadHandle {
  /** Abort the upload (tus DELETEs the staging session if possible). */
  abort: () => Promise<void>;
}

/**
 * Start an offline-ingest upload session and stream chunks to the
 * backend via tus 1.0.
 *
 * Returns an `UploadHandle` whose `abort()` cancels in-flight chunks.
 * Callbacks are invoked exactly as tus-js-client fires them:
 *   - `onProgress` per PATCH ack
 *   - `onComplete` once the final byte is acked
 *   - `onError` if creation or any PATCH retries are exhausted
 */
export function uploadOfflineAudio(opts: UploadOfflineAudioOptions): UploadHandle {
  const endpoint = `/api/meetings/${opts.meetingId}/recordings/offline_upload`;
  const upload = new tus.Upload(opts.file, {
    endpoint,
    retryDelays: [0, 3000, 5000, 10000, 20000],
    chunkSize: 5 * 1024 * 1024, // 5 MiB chunks — balance between request overhead and resume granularity
    metadata: {
      filename: opts.file.name,
      mimetype: opts.file.type || "application/octet-stream",
      actual_started_at: opts.actualStartedAt.toISOString(),
    },
    onProgress: (bytesUploaded, bytesTotal) => {
      opts.onProgress?.({ bytesUploaded, bytesTotal });
    },
    onSuccess: () => {
      opts.onComplete?.();
    },
    onError: (rawError) => {
      opts.onError?.(_toUploadError(rawError));
    },
  });
  upload.start();

  return {
    abort: async () => {
      await upload.abort(true);
    },
  };
}

/**
 * Translate a tus-js-client error into the project's canonical
 * `OfflineIngestUploadError` shape so the dialog can surface a localized
 * error via the existing `localizedErrorMessage` helper.
 */
function _toUploadError(rawError: unknown): OfflineIngestUploadError {
  // tus-js-client surfaces server-side responses on `error.originalResponse`;
  // when a tus PATCH / POST returns 4xx with our `{error_code, message}`
  // envelope we reach through it. For network / unknown errors we fall
  // back to a generic code so callers don't crash on missing fields.
  const err = rawError as {
    message?: string;
    originalResponse?: {
      getStatus: () => number;
      getBody: () => string;
    };
  };
  const status = err.originalResponse?.getStatus?.() ?? 0;
  let errorCode = status > 0 ? `http.${status}` : "offline_ingest.network";
  let message = err.message ?? "Offline ingest upload failed.";

  const body = err.originalResponse?.getBody?.();
  if (body) {
    try {
      const parsed = JSON.parse(body) as {
        error_code?: string;
        message?: string;
        detail?: { error_code?: string; message?: string };
      };
      const code = parsed.error_code ?? parsed.detail?.error_code;
      const msg = parsed.message ?? parsed.detail?.message;
      if (typeof code === "string") errorCode = code;
      if (typeof msg === "string" && msg.length > 0) message = msg;
    } catch {
      // Non-JSON body — keep the generic decoding.
    }
  }
  return new OfflineIngestUploadError(errorCode, message, status);
}
