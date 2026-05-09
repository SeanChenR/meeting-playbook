/**
 * Historical transcript_chunk fetch — used after a session completes so the
 * meeting detail page can show what was transcribed in past sessions.
 *
 * Live transcript chunks (via WebSocket) flow through `useMeetingSession`;
 * this lib is purely for the past-session replay surface.
 */

import type { TranscriptChunkMessage } from "./session-ws";

export interface TranscriptChunkRow {
  id: string;
  meeting_id: string;
  speaker: "me" | "counterparty" | "system";
  text: string;
  started_at: string;
  ended_at: string;
  asr_provider_used: string;
  confidence: number | null;
}

export class TranscriptsApiError extends Error {
  status: number;
  errorCode: string | undefined;
  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<TranscriptsApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new TranscriptsApiError(
    resp.status,
    body.error_code,
    body.message ?? `HTTP ${resp.status}`,
  );
}

export async function listTranscriptChunks(meetingId: string): Promise<TranscriptChunkRow[]> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/transcript_chunks`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as TranscriptChunkRow[];
}

export function transcriptChunksQueryOptions(meetingId: string, enabled: boolean) {
  return {
    queryKey: ["transcripts", meetingId] as const,
    queryFn: () => listTranscriptChunks(meetingId),
    enabled,
  };
}

/** Convert a row (from REST) to the TranscriptChunkMessage shape used by TranscriptPane. */
export function rowToMessage(row: TranscriptChunkRow): TranscriptChunkMessage {
  return {
    type: "transcript_chunk",
    meeting_id: row.meeting_id,
    speaker: row.speaker,
    text: row.text,
    started_at: row.started_at,
    ended_at: row.ended_at,
    asr_provider_used: row.asr_provider_used,
    confidence: row.confidence,
  };
}
