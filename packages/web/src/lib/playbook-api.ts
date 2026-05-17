/**
 * Playbook REST client.
 *
 * Wraps `fetch` against `/api/meetings/{id}/playbook`. Errors are normalized
 * to `PlaybookApiError` so UI code can resolve `errorCode` through
 * `localizedErrorMessage(t)`. Mutation hook invalidates the
 * `["playbook", meetingId]` cache on success so any mounted view refetches.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

export interface Playbook {
  id: string;
  meeting_id: string;
  free_form_markdown: string;
  objective: string;
  counterparty_profile: string;
  anticipated_topics: string;
  anticipated_objections: string;
  talking_points: string;
  red_lines: string;
  created_at: string;
  updated_at: string;
  /**
   * Slice-20c: `true` when the live attachment-set hash differs from the
   * snapshot captured at generation time. The pane shows a "regenerate"
   * banner when this is true.
   */
  is_stale?: boolean;
}

export interface PlaybookUpsertPayload {
  free_form_markdown: string;
  objective: string;
  counterparty_profile: string;
  anticipated_topics: string;
  anticipated_objections: string;
  talking_points: string;
  red_lines: string;
}

export class PlaybookApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<PlaybookApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new PlaybookApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function getPlaybook(meetingId: string): Promise<Playbook> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/playbook`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Playbook;
}

export async function upsertPlaybook(
  meetingId: string,
  payload: PlaybookUpsertPayload,
): Promise<Playbook> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/playbook`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Playbook;
}

export function playbookQueryOptions(meetingId: string) {
  return {
    queryKey: ["playbook", meetingId] as const,
    queryFn: () => getPlaybook(meetingId),
  };
}

export function useUpsertPlaybookMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PlaybookUpsertPayload) => upsertPlaybook(meetingId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbook", meetingId] });
    },
  });
}

/**
 * Slice-20c: trigger an LLM regeneration of the playbook against the
 * meeting's current attachment set. Used by the stale-banner button.
 * Backend returns the new draft + clears the `is_stale` flag.
 */
export async function regeneratePlaybook(meetingId: string): Promise<Playbook> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/playbook/regenerate`, {
    method: "POST",
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Playbook;
}

export function useRegeneratePlaybookMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => regeneratePlaybook(meetingId),
    onSuccess: (data) => {
      queryClient.setQueryData(["playbook", meetingId], data);
    },
  });
}
