/**
 * Transcript edit API helper — slice-16 task 7.1.
 *
 * Wraps `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}` with the
 * project's error envelope conventions: 422 responses surface as a
 * thrown `TranscriptEditApiError` carrying `error_code` + `message` so
 * the calling component can pipe it through `localizedErrorMessage`.
 */

export interface PatchedChunk {
  id: string;
  text: string;
  text_edited_at: string | null;
}

export class TranscriptEditApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  constructor(status: number, errorCode: string, message: string) {
    super(message);
    this.name = "TranscriptEditApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export async function patchTranscriptChunk(
  meetingId: string,
  chunkId: string,
  text: string,
): Promise<PatchedChunk> {
  const resp = await fetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/transcript_chunks/${encodeURIComponent(chunkId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
  );
  if (!resp.ok) {
    let errorCode = `http.${resp.status}`;
    let message = resp.statusText;
    try {
      const body = await resp.json();
      if (body && typeof body === "object") {
        if (typeof body.error_code === "string") errorCode = body.error_code;
        if (typeof body.message === "string") message = body.message;
      }
    } catch {
      // body wasn't JSON — keep defaults
    }
    throw new TranscriptEditApiError(resp.status, errorCode, message);
  }
  return (await resp.json()) as PatchedChunk;
}
