/**
 * summary-api — slice-10 React Query options + POST helper for summary.
 *
 * GET responses come in three shapes (see meeting-summary spec):
 *   1. 200 + Summary (id, meeting_id, markdown, generated_at, is_stale)
 *   2. 200 + SummaryPending (`{status: "pending", generated_at: null}`)
 *   3. 404 + envelope `{error_code: "summary.not_found", ...}` → queryFn
 *      returns `null` so React Query treats it as a successful empty
 *      result (caller renders the "generate now" empty state).
 */

export interface Summary {
  id: string;
  meeting_id: string;
  markdown: string;
  generated_at: string;
  is_stale: boolean;
}

export interface SummaryPending {
  status: "pending";
  generated_at: null;
}

export type SummaryResponse = Summary | SummaryPending | null;

export class SummaryApiError extends Error {
  status: number;
  errorCode: string | undefined;
  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<SummaryApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new SummaryApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function fetchSummary(meetingId: string): Promise<SummaryResponse> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/summary`);
  if (resp.status === 404) {
    // summary.not_found is a normal "no row yet" state — return null so
    // the SummaryPane can render the empty / generate-now UI.
    return null;
  }
  if (!resp.ok) throw await _envelopeError(resp);
  const body = (await resp.json()) as Summary | SummaryPending;
  return body;
}

interface QueryOptionsExtras {
  enabled: boolean;
  // React Query v5: refetchInterval callback receives the Query instance,
  // not the raw `data`. Use `q.state.data` to read the current cached value.
  // Numeric or `false` for static intervals.
  refetchInterval?: number | false | ((q: { state: { data?: SummaryResponse } }) => number | false);
}

export function summaryQueryOptions(meetingId: string, opts: QueryOptionsExtras) {
  return {
    queryKey: ["summary", meetingId] as const,
    queryFn: () => fetchSummary(meetingId),
    enabled: opts.enabled,
    refetchInterval: opts.refetchInterval,
  };
}

/** POST trigger / regenerate. Returns void on 202; throws SummaryApiError on 409 / 404. */
export async function regenerateSummary(meetingId: string): Promise<void> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/summary`, {
    method: "POST",
  });
  if (resp.status === 202) return;
  throw await _envelopeError(resp);
}

/** Type guard: distinguishes the in-flight `pending` shape from a real Summary. */
export function isPendingSummary(s: SummaryResponse | undefined): s is SummaryPending {
  return s !== null && s !== undefined && (s as SummaryPending).status === "pending";
}
