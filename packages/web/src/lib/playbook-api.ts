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
  /**
   * Slice-23: previous-version snapshot fields. Populated only after a
   * regenerate run; user-save (`PUT /playbook`) NEVER touches them. The
   * UI computes the diff client-side from
   * `previous_free_form_markdown` vs `free_form_markdown`.
   *
   * `has_previous_version` is derived server-side
   * (`= previous_free_form_markdown !== null`) so the UI never has to
   * null-check inline.
   */
  previous_free_form_markdown?: string | null;
  previous_updated_at?: string | null;
  has_previous_version?: boolean;
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

/**
 * Slice-23: clear the previous-version snapshot ("accept new draft").
 * Backend returns the updated `PlaybookRead` with `previous_*` = null.
 */
export async function discardPreviousPlaybook(meetingId: string): Promise<Playbook> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/playbook/discard_previous`,
    { method: "POST" },
  );
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Playbook;
}

/**
 * Slice-23: swap the previous-version snapshot back into the current
 * draft ("restore old version"). Backend overwrites `free_form_markdown`
 * + `attachment_hash_snapshot` and clears `previous_*`.
 */
export async function restorePreviousPlaybook(meetingId: string): Promise<Playbook> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/playbook/restore_previous`,
    { method: "POST" },
  );
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as Playbook;
}

export function useDiscardPreviousPlaybookMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => discardPreviousPlaybook(meetingId),
    onSuccess: (data) => {
      queryClient.setQueryData(["playbook", meetingId], data);
    },
  });
}

export function useRestorePreviousPlaybookMutation(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => restorePreviousPlaybook(meetingId),
    onSuccess: (data) => {
      queryClient.setQueryData(["playbook", meetingId], data);
    },
  });
}
