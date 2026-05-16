/**
 * Tag REST client — slice-17 task 5.1.
 *
 * Wraps the `/api/tags` and `/api/meetings/{id}/tags` endpoints. Errors are
 * normalized to `ApiError` so UI code can resolve `errorCode` through
 * `localizedErrorMessage(t)`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  color: string;
  created_at: string;
  /** Present only when `?with_meeting_count=true` was requested. */
  meeting_count?: number;
}

export interface MeetingTagAttachment {
  meeting_id: string;
  tag_id: string;
  attached_at: string;
}

export class ApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<ApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new ApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function listTags(options?: { withMeetingCount?: boolean }): Promise<Tag[]> {
  const params = options?.withMeetingCount ? "?with_meeting_count=true" : "";
  const resp = await fetch(`/api/tags${params}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Tag[];
}

export async function createTag(payload: { name: string; color: string }): Promise<Tag> {
  const resp = await fetch("/api/tags", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Tag;
}

export async function updateTag(
  tagId: string,
  payload: { name?: string; color?: string },
): Promise<Tag> {
  const resp = await fetch(`/api/tags/${encodeURIComponent(tagId)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Tag;
}

export async function deleteTag(tagId: string): Promise<void> {
  const resp = await fetch(`/api/tags/${encodeURIComponent(tagId)}`, { method: "DELETE" });
  if (!resp.ok) throw await _envelopeError(resp);
}

export async function attachTag(meetingId: string, tagId: string): Promise<MeetingTagAttachment> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/tags`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ tag_id: tagId }),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as MeetingTagAttachment;
}

export async function detachTag(meetingId: string, tagId: string): Promise<void> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/tags/${encodeURIComponent(tagId)}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw await _envelopeError(resp);
}

/**
 * Query key conventions:
 *   - `["tags"]` — all user tags (no meeting count)
 *   - `["tags", "with-count"]` — settings page list
 *
 * Mutations invalidate both keys + the meetings caches so attach/detach
 * surfaces in the meeting list and detail views immediately.
 */
export function tagsListQueryOptions(options?: { withMeetingCount?: boolean }) {
  if (options?.withMeetingCount) {
    return {
      queryKey: ["tags", "with-count"] as const,
      queryFn: () => listTags({ withMeetingCount: true }),
    };
  }
  return {
    queryKey: ["tags"] as const,
    queryFn: () => listTags(),
  };
}

export function useTagsListQuery(options?: { withMeetingCount?: boolean }) {
  return useQuery(tagsListQueryOptions(options));
}

function _invalidateTagsAndMeetings(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["tags"] });
  qc.invalidateQueries({ queryKey: ["meetings"] });
}

export function useCreateTagMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTag,
    onSuccess: () => _invalidateTagsAndMeetings(qc),
  });
}

export function useUpdateTagMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      tagId,
      payload,
    }: {
      tagId: string;
      payload: { name?: string; color?: string };
    }) => updateTag(tagId, payload),
    onSuccess: () => _invalidateTagsAndMeetings(qc),
  });
}

export function useDeleteTagMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTag,
    onSuccess: () => _invalidateTagsAndMeetings(qc),
  });
}

export function useAttachTagMutation(meetingId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) => attachTag(meetingId, tagId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      qc.invalidateQueries({ queryKey: ["meetings", meetingId] });
      qc.invalidateQueries({ queryKey: ["tags", "with-count"] });
    },
  });
}

export function useDetachTagMutation(meetingId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) => detachTag(meetingId, tagId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      qc.invalidateQueries({ queryKey: ["meetings", meetingId] });
      qc.invalidateQueries({ queryKey: ["tags", "with-count"] });
    },
  });
}
