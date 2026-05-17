/**
 * Meeting-link REST client — slice-21 task 4.1.
 *
 * Three helpers wrap the three endpoints exposed by
 * `packages/backend/meeting_playbook/meeting_links/router.py`:
 *
 *   - listLinks(meetingId)     → GET    /api/meetings/{id}/links
 *   - createLink(meetingId, …) → POST   /api/meetings/{id}/links
 *   - deleteLink(meetingId, …) → DELETE /api/meetings/{id}/links/{link_id}
 *
 * Errors are normalised to `MeetingLinkApiError` so UI code can resolve
 * `errorCode` through `localizedErrorMessage(t)` and keep the modal open
 * on 409/422 paths.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

export interface MeetingLinkView {
  link_id: string;
  other_meeting_id: string;
  other_meeting_title: string;
  other_meeting_scheduled_start_at: string;
  link_type: "related";
  created_at: string;
}

export interface CreateLinkResponse {
  link_id: string;
}

export class MeetingLinkApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<MeetingLinkApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore — keep defaults
  }
  return new MeetingLinkApiError(
    resp.status,
    body.error_code,
    body.message ?? `HTTP ${resp.status}`,
  );
}

export async function listLinks(meetingId: string): Promise<MeetingLinkView[]> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/links`);
  if (!resp.ok) throw await _envelopeError(resp);
  const body = (await resp.json()) as { links: MeetingLinkView[] };
  return body.links;
}

export async function createLink(
  meetingId: string,
  toMeetingId: string,
): Promise<CreateLinkResponse> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/links`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ to_meeting_id: toMeetingId }),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as CreateLinkResponse;
}

export async function deleteLink(meetingId: string, linkId: string): Promise<void> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/links/${encodeURIComponent(linkId)}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw await _envelopeError(resp);
}

/**
 * React Query options factory for the bidirectional links list. Components
 * call `useQuery(meetingLinksQueryOptions(meetingId))`; mutations invalidate
 * by the same key so the section refreshes inline after add/delete.
 */
export function meetingLinksQueryOptions(meetingId: string) {
  return {
    queryKey: ["meetings", meetingId, "links"] as const,
    queryFn: () => listLinks(meetingId),
  };
}

export function useCreateLinkMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (toMeetingId: string) => createLink(meetingId, toMeetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings", meetingId, "links"] });
    },
  });
}

export function useDeleteLinkMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: string) => deleteLink(meetingId, linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings", meetingId, "links"] });
    },
  });
}
