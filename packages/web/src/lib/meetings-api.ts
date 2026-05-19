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

/**
 * Derived lifecycle bucket — surfaced by the backend on every meeting
 * response. Drives Kanban column placement + the single card chip.
 *
 *   upcoming        — scheduled meeting whose scheduled_start_at >= now
 *   needs_recording — scheduled meeting whose scheduled_start_at < now
 *   completed       — any meeting whose status is in_progress or completed
 *
 * Computed server-side from `status` + `scheduled_start_at` against the
 * backend's UTC wall clock, so frontend rendering is single-source.
 */
export type MeetingBucket = "upcoming" | "needs_recording" | "completed";

export interface MeetingTagSummary {
  id: string;
  name: string;
  color: string;
}

export interface Meeting {
  id: string;
  user_id: string;
  title: string;
  counterparty_display_name: string;
  me_display_name: string;
  status: MeetingStatus;
  /** Derived lifecycle bucket — see {@link MeetingBucket}. Backend always
   * emits this (computed_field on `MeetingRead`), but the TS type leaves
   * it optional so existing test fixtures don't need backfill — UI code
   * MUST go through `resolveMeetingBucket(meeting)` which falls back to
   * the client-side compute when `bucket` is absent. */
  bucket?: MeetingBucket;
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
  // Slice-17: every list / detail payload includes the meeting's tags.
  // Marked optional so legacy test fixtures that pre-date the tag system
  // do not need to be back-filled; consumers should treat `undefined` as
  // "no tags attached" (equivalent to an empty array). Backend always
  // emits `[]` when no tags are attached.
  tags?: MeetingTagSummary[];
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
  // Slice-20b: when set, the backend fetches the calendar event, runs the
  // Playbook generator synchronously, and writes the resulting draft into
  // the playbook row (replacing the slice-04 auto-create empty draft).
  calendar_event_id?: string;
  // Slice-20b: ids of pre-uploaded attachments (slice-20a) that should be
  // associated with the new meeting. Each id MUST be owned by the current
  // user and have `meeting_id IS NULL` — otherwise the backend returns
  // HTTP 422 with `error_code: attachment.not_attachable`.
  attachments?: string[];
  // Slice-21: ids of existing meetings to attach as `related` links at
  // create time. Each id MUST reference a meeting owned by the current
  // user. Bidirectional semantics apply: linking A→B from the create
  // form makes B's detail page also show A under "Related meetings".
  links?: string[];
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

/**
 * Slice-17 added `tagIds` to AND-filter by tag attachment.
 * Slice-18 added home-page filters (`scheduled_date / status / pending /
 * order / limit`). Both sets are exposed as the same `MeetingListFilters`
 * object; the backend dispatches between the tag-aware path and the
 * filter path based on whether `tagIds` is present.
 */
export interface MeetingListFilters {
  tagIds?: string[];
  /** YYYY-MM-DD in Asia/Taipei day boundary. */
  scheduled_date?: string;
  status?: MeetingStatus;
  pending?: boolean;
  /** e.g. `"scheduled_start_at:asc"` or `"updated_at:desc"`. */
  order?: string;
  limit?: number;
}

export async function listMeetings(filters?: MeetingListFilters): Promise<Meeting[]> {
  const params = new URLSearchParams();
  if (filters?.tagIds && filters.tagIds.length > 0) {
    params.set("tag_ids", filters.tagIds.join(","));
  }
  if (filters?.scheduled_date) params.set("scheduled_date", filters.scheduled_date);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.pending !== undefined) params.set("pending", String(filters.pending));
  if (filters?.order) params.set("order", filters.order);
  if (filters?.limit !== undefined) params.set("limit", String(filters.limit));
  const url = params.toString() ? `/api/meetings?${params.toString()}` : "/api/meetings";
  const resp = await fetch(url);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Meeting[];
}

/**
 * Slice-18 home regions each call this with a different filter combo.
 * Cache key includes the filter object so regions don't share entries.
 */
export function meetingsFilteredQueryOptions(filters: MeetingListFilters) {
  return {
    queryKey: ["meetings", "filtered", filters] as const,
    queryFn: () => listMeetings(filters),
  };
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
export function meetingsListQueryOptions(options?: { tagIds?: string[] }) {
  const tagIds = options?.tagIds ?? [];
  // Preserve the historical `["meetings"]` key when no tag filter is active
  // so existing `invalidateQueries({ queryKey: ["meetings"] })` calls and
  // the slice-3 queries.test snapshot keep matching.
  if (tagIds.length === 0) {
    return {
      queryKey: ["meetings"] as const,
      queryFn: () => listMeetings(),
    };
  }
  return {
    queryKey: ["meetings", { tagIds: tagIds.slice().sort() }] as const,
    queryFn: () => listMeetings({ tagIds }),
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

// ─── Audio playback URL helpers — slice-25 task 3.1 ─────────────────────

export interface AudioUrlParams {
  /** Seconds (epoch-relative) chunk start; appended as ?start=. */
  start?: number;
  /** Seconds (epoch-relative) chunk end; appended as ?end=. */
  end?: number;
}

function _appendStartEnd(url: string, params: AudioUrlParams | undefined): string {
  if (!params) return url;
  const q = new URLSearchParams();
  if (params.start !== undefined) q.set("start", String(params.start));
  if (params.end !== undefined) q.set("end", String(params.end));
  const qs = q.toString();
  return qs ? `${url}?${qs}` : url;
}

/**
 * URL for a single per-recording audio stream (existing endpoint).
 * Used for me / counterparty sources in the mini-player source toggle.
 */
export function recordingAudioUrl(
  meetingId: string,
  recordingId: string,
  params?: AudioUrlParams,
): string {
  const base = `/api/meetings/${encodeURIComponent(meetingId)}/recordings/${encodeURIComponent(
    recordingId,
  )}/audio`;
  return _appendStartEnd(base, params);
}

/**
 * URL for the dual-stream mixed playback endpoint — slice-25 design D4.
 * Server lazy-mixes `me.wav` + `counterparty.wav` on first request.
 */
export function mixedAudioUrl(meetingId: string, params?: AudioUrlParams): string {
  const base = `/api/meetings/${encodeURIComponent(meetingId)}/recordings/mixed/audio`;
  return _appendStartEnd(base, params);
}
