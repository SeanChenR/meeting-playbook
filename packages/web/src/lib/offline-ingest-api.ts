/**
 * Offline-ingest progress polling client (slice-14 task 5.2).
 *
 * Mirrors the `voice-enrollment-api.ts` pattern: a thin `fetch` wrapper
 * that translates `{error_code, message}` envelopes into a typed
 * `OfflineIngestApiError`. The upload dialog calls
 * `getOfflineIngestProgress(meetingId)` every 3 seconds after the tus
 * upload reaches 100% so the user sees `transcoding → asr_running →
 * completed` state transitions.
 */

export class OfflineIngestApiError extends Error {
  readonly errorCode: string;
  readonly statusCode: number;

  constructor(errorCode: string, message: string, statusCode: number) {
    super(message);
    this.name = "OfflineIngestApiError";
    this.errorCode = errorCode;
    this.statusCode = statusCode;
  }
}

export type OfflineIngestState =
  | "uploading"
  | "transcoding"
  | "asr_running"
  | "completed"
  | "failed"
  | "idle";

export interface OfflineIngestProgress {
  state: OfflineIngestState;
  chunks_processed?: number;
  chunks_total?: number;
  error_code?: string;
}

/**
 * Fetch the current offline-ingest pipeline state for one meeting.
 *
 * Returns the parsed `OfflineIngestProgress` shape on 2xx. Throws
 * `OfflineIngestApiError` on any non-2xx so the dialog can render a
 * localized message via `localizedErrorMessage(error.errorCode, t)`.
 */
export async function getOfflineIngestProgress(meetingId: string): Promise<OfflineIngestProgress> {
  const response = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/offline_ingest_progress`,
  );

  if (response.ok) {
    return (await response.json()) as OfflineIngestProgress;
  }

  let errorCode = `http.${response.status}`;
  let message = `Failed to fetch offline ingest progress (HTTP ${response.status})`;
  try {
    const body = (await response.json()) as Partial<{
      error_code: string;
      message: string;
      detail: { error_code?: string; message?: string };
    }>;
    const code = body.error_code ?? body.detail?.error_code;
    const msg = body.message ?? body.detail?.message;
    if (typeof code === "string") errorCode = code;
    if (typeof msg === "string" && msg.length > 0) message = msg;
  } catch {
    // Non-JSON body — keep the generic message.
  }
  throw new OfflineIngestApiError(errorCode, message, response.status);
}
