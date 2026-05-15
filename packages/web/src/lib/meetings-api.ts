import { useMutation, useQueryClient } from "@tanstack/react-query";

/**
 * Meeting REST client.
 *
 * Wraps `fetch` against the relative `/api/meetings` path; Vite dev server
 * proxies to the Bun gateway, which then forwards to FastAPI with the
 * `X-User-Id` injected from the Better Auth session.
 *
 * Errors are normalized to `MeetingApiError` so UI code can resolve
 * `errorCode` through `localizedErrorMessage(t)`.
 */

export type MeetingStatus = "scheduled" | "in_progress" | "completed";

export interface Meeting {
  id: string;
  user_id: string;
  title: string;
  counterparty_display_name: string;
  me_display_name: string;
  status: MeetingStatus;
  asr_provider: string;
  calendar_event_id: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  // Slice-7 introduced these; slice-15 made `scheduled_start_at` required
  // at the DB layer (migration 0012 + Pydantic NOT NULL) so the meetings
  // list / Kanban / calendar views can drop their `?? created_at`
  // fallback. `scheduled_end_at` stays nullable.
  scheduled_start_at: string;
  scheduled_end_at: string | null;
}

export interface RecordingSummary {
  id: string;
  meeting_id: string;
  stream: string;
  started_at: string;
  deleted_at: string | null;
}

/**
 * Slice-11: GET /api/meetings/{id} returns this superset (mirrors backend
 * `MeetingDetailRead`). The list endpoint still returns plain `Meeting`.
 *
 * Slice-16 task 10.7: `recordings` carries the meeting's recording rows
 * so the audio mini-player can construct `/api/.../audio` URLs and
 * compute chunk-relative seek offsets.
 */
export interface MeetingDetail extends Meeting {
  recordings_available: boolean;
  rerun_asr_pending: boolean;
  recordings?: RecordingSummary[];
}

export interface MeetingPatchPayload {
  // Slice-15: PATCH now accepts every mutable field. All keys are
  // optional — the form sends only the changed entries.
  title?: string;
  counterparty_display_name?: string;
  me_display_name?: string;
  scheduled_start_at?: string;
  scheduled_end_at?: string | null;
  asr_provider?: string;
}

export interface MeetingCreatePayload {
  title: string;
  counterparty_display_name: string;
  me_display_name: string;
  // Slice-7: optional ISO 8601 timestamps for the planned meeting time.
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
}

export class MeetingApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<MeetingApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore — keep defaults
  }
  return new MeetingApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function listMeetings(): Promise<Meeting[]> {
  const resp = await fetch("/api/meetings");
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Meeting[];
}

export async function getMeeting(id: string): Promise<MeetingDetail> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(id)}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as MeetingDetail;
}

export async function patchMeeting(
  id: string,
  payload: MeetingPatchPayload,
): Promise<MeetingDetail> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as MeetingDetail;
}

export async function createMeeting(payload: MeetingCreatePayload): Promise<Meeting> {
  const resp = await fetch("/api/meetings", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Meeting;
}

export async function deleteMeeting(id: string): Promise<void> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw await _envelopeError(resp);
}

/**
 * Query keys form the cache invalidation contract.
 *
 * - `["meetings"]` — list
 * - `["meetings", id]` — single row
 *
 * Mutations invalidate by these keys; pages just feed the query options into
 * `useQuery` and never compute keys themselves.
 */
export function meetingsListQueryOptions() {
  return {
    queryKey: ["meetings"] as const,
    queryFn: listMeetings,
  };
}

export function meetingQueryOptions(id: string) {
  return {
    queryKey: ["meetings", id] as const,
    queryFn: () => getMeeting(id),
  };
}

/**
 * Mutation hooks. Each one invalidates the relevant cache slice on success
 * so any mounted list / detail view refetches without manual refetch wiring.
 */
export function useCreateMeetingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMeeting,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });
}

export function useDeleteMeetingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteMeeting,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      queryClient.invalidateQueries({ queryKey: ["meetings", id] });
    },
  });
}

/**
 * Slice-11: PATCH `/api/meetings/{id}` — used by the AsrProviderSelector.
 * Updates the cached single-meeting query in place from the response so the
 * UI doesn't need to refetch.
 */
export function usePatchMeetingMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MeetingPatchPayload) => patchMeeting(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["meetings", id], updated);
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });
}
