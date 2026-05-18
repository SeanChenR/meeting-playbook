/**
 * Recording-index REST client (P4 IA refactor).
 *
 * Backed by:
 *   GET  /api/recordings                        — list current user's recordings
 *                                                 inside the Recording window
 *   POST /api/recordings/batch-download         — streaming ZIP of selected ids
 *
 * Single-row download reuses the existing per-meeting audio endpoint
 * (`GET /api/meetings/:id/recordings/:rid/audio`); no flat audio route is
 * introduced (per design.md "Single-recording download reuses existing
 * endpoint").
 *
 * Errors are normalized to `RecordingApiError` so UI code can resolve
 * `errorCode` through `localizedErrorMessage(t)`.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

export type RecordingStream = "me" | "counterparty";

export interface RecordingSummary {
  id: string;
  meeting_id: string;
  meeting_title: string;
  counterparty_label: string;
  captured_at: string;
  duration_ms: number;
  byte_size: number;
  stream: RecordingStream;
}

export interface RecordingListResponse {
  recordings: RecordingSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface RecordingListParams {
  since?: string | undefined;
  until?: string | undefined;
  search?: string | undefined;
  page?: number | undefined;
}

export class RecordingApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<RecordingApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore — backend may not have produced a JSON body
  }
  return new RecordingApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export function recordingAudioUrl(meetingId: string, recordingId: string): string {
  return `/api/meetings/${encodeURIComponent(meetingId)}/recordings/${encodeURIComponent(recordingId)}/audio`;
}

function _buildListUrl(params: RecordingListParams): string {
  const search = new URLSearchParams();
  if (params.since) search.set("since", params.since);
  if (params.until) search.set("until", params.until);
  if (params.search) search.set("search", params.search);
  if (params.page !== undefined) search.set("page", String(params.page));
  const qs = search.toString();
  return qs ? `/api/recordings?${qs}` : "/api/recordings";
}

export async function listRecordings(params: RecordingListParams): Promise<RecordingListResponse> {
  const resp = await fetch(_buildListUrl(params));
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as RecordingListResponse;
}

export function recordingsListQueryOptions(params: RecordingListParams) {
  return {
    queryKey: [
      "recordings",
      "list",
      params.since ?? null,
      params.until ?? null,
      params.search ?? null,
      params.page ?? 1,
    ] as const,
    queryFn: () => listRecordings(params),
  };
}

export function useRecordingsList(params: RecordingListParams) {
  return useQuery(recordingsListQueryOptions(params));
}

export interface BatchDownloadPayload {
  recording_ids: string[];
}

/**
 * Trigger a streaming download of the selected recordings as a ZIP. The
 * browser saves the file using the filename embedded in the response's
 * Content-Disposition header (falls back to `recordings.zip` when absent).
 */
export async function batchDownloadRecordings(payload: BatchDownloadPayload): Promise<void> {
  const resp = await fetch("/api/recordings/batch-download", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);

  const blob = await resp.blob();
  const filename = _parseFilename(resp.headers.get("content-disposition")) ?? "recordings.zip";
  _saveBlobToDisk(blob, filename);
}

function _parseFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match?.[1] ?? null;
}

function _saveBlobToDisk(blob: Blob, filename: string): void {
  if (typeof document === "undefined") return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function useBatchDownloadMutation() {
  return useMutation({
    mutationFn: (payload: BatchDownloadPayload) => batchDownloadRecordings(payload),
  });
}
