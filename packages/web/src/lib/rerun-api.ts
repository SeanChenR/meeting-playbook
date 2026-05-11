/**
 * rerun-api — slice-11 React Query options for ASR re-run + status polling.
 *
 * Mirrors the slice-10 summary-api shape so the polling pattern stays
 * recognizable: `useQuery(rerunStatusQueryOptions(meetingId, opts))` with a
 * `refetchInterval` callback that polls every 1s while status is pending,
 * and a POST helper that returns void on 202.
 *
 * Backend endpoints (see meetings/router.py slice-11 additions):
 *   POST /api/meetings/{id}/rerun_asr       → 202 / 409 / 410 / 422 / 404
 *   GET  /api/meetings/{id}/rerun_asr_status → 200 {status, processed, total}
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

export type RerunStatusValue = "idle" | "pending" | "failed";

export interface RerunStatus {
  status: RerunStatusValue;
  chunks_processed: number;
  chunks_total: number;
}

export class RerunApiError extends Error {
  status: number;
  errorCode: string | undefined;
  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<RerunApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new RerunApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function fetchRerunStatus(meetingId: string): Promise<RerunStatus> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/rerun_asr_status`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as RerunStatus;
}

/** POST trigger. Returns void on 202; throws RerunApiError on 409/410/422/404. */
export async function startRerun(meetingId: string): Promise<void> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/rerun_asr`, {
    method: "POST",
  });
  if (resp.status === 202) return;
  throw await _envelopeError(resp);
}

interface RerunStatusOptionsExtras {
  enabled: boolean;
  /**
   * React Query v5 callback signature: receives the Query instance, not
   * the raw `data`. Returning a number sets the next poll delay; returning
   * `false` stops polling.
   */
  refetchInterval?: number | false | ((q: { state: { data?: RerunStatus } }) => number | false);
}

export function rerunStatusQueryOptions(meetingId: string, opts: RerunStatusOptionsExtras) {
  return {
    queryKey: ["rerun_status", meetingId] as const,
    queryFn: () => fetchRerunStatus(meetingId),
    enabled: opts.enabled,
    refetchInterval: opts.refetchInterval,
  };
}

/** Type guard so callers can branch without re-checking the literal string. */
export function isRerunPending(s: RerunStatus | null | undefined): s is RerunStatus {
  return s !== null && s !== undefined && s.status === "pending";
}

/**
 * Side-effect hook: when polled status transitions from pending → idle,
 * invalidate the transcript chunks cache so the TranscriptPane refetches
 * the new content immediately. Mirrors the slice-10 summary→meeting cache
 * invalidation pattern.
 */
export function useTranscriptInvalidationOnRerunComplete(
  meetingId: string,
  status: RerunStatusValue | null | undefined,
): void {
  const queryClient = useQueryClient();
  const lastStatusRef = useRef<RerunStatusValue | null | undefined>(undefined);
  useEffect(() => {
    if (lastStatusRef.current === "pending" && status === "idle") {
      queryClient.invalidateQueries({ queryKey: ["transcripts", meetingId] });
      // Also refresh the meeting row so `rerun_asr_pending` flips false.
      queryClient.invalidateQueries({ queryKey: ["meetings", meetingId] });
    }
    lastStatusRef.current = status;
  }, [meetingId, status, queryClient]);
}
