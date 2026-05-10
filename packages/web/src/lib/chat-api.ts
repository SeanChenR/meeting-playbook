/**
 * Chat history fetch — used by AdvisorPane to hydrate persisted
 * conversation when the meeting detail page mounts.
 *
 * Live messages flow through the WebSocket via `useMeetingSession`; this
 * module supplies the initial history snapshot from the backend GET API.
 */

export interface ChatMessage {
  id: string;
  meeting_id: string;
  role: "user" | "advisor";
  content: string;
  created_at: string;
}

export class ChatApiError extends Error {
  status: number;
  errorCode: string | undefined;
  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<ChatApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore — body might not be JSON on a 5xx HTML page
  }
  return new ChatApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function listChatMessages(meetingId: string): Promise<ChatMessage[]> {
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/chat_messages`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as ChatMessage[];
}

export function chatMessagesQueryOptions(meetingId: string, enabled: boolean) {
  return {
    queryKey: ["chat_messages", meetingId] as const,
    queryFn: () => listChatMessages(meetingId),
    enabled,
  };
}
