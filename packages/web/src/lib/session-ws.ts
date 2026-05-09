/**
 * Thin WebSocket wrapper for the meeting session.
 *
 * Mirrors the Pydantic discriminated union in
 * `packages/backend/meeting_playbook/sessions/messages.py`. Keep both shapes
 * in lockstep — the spec example matrix is the contract.
 */

// ─── Server → client message types ─────────────────────────────────────────

export type MeetingStartedMessage = {
  type: "meeting_started";
  meeting_id: string;
};

export type TranscriptChunkMessage = {
  type: "transcript_chunk";
  meeting_id: string;
  speaker: "me" | "counterparty" | "system";
  text: string;
  started_at: string;
  ended_at: string;
  asr_provider_used: string;
  confidence: number | null;
};

export type SilenceWarningMessage = {
  type: "silence_warning";
  meeting_id: string;
  since: string;
};

export type MeetingEndedMessage = {
  type: "meeting_ended";
  meeting_id: string;
};

export type ErrorMessage = {
  type: "error";
  error_code: string;
  message: string;
};

export type SessionMessage =
  | MeetingStartedMessage
  | TranscriptChunkMessage
  | SilenceWarningMessage
  | MeetingEndedMessage
  | ErrorMessage;

// ─── Client → server message types ─────────────────────────────────────────

export type StartMeetingMessage = { type: "start_meeting"; meeting_id: string };
export type EndMeetingMessage = { type: "end_meeting"; meeting_id: string };

export type ClientMessage = StartMeetingMessage | EndMeetingMessage;

// ─── Wrapper ───────────────────────────────────────────────────────────────

export interface SessionSocket {
  send(message: ClientMessage): void;
  close(): void;
  onOpen: (() => void) | null;
  onMessage: ((msg: SessionMessage) => void) | null;
  onError: ((err: unknown) => void) | null;
  onClose: ((ev: CloseEvent) => void) | null;
}

function _wsUrl(meetingId: string): string {
  if (typeof window === "undefined") {
    return `ws://localhost:3001/api/meetings/${encodeURIComponent(meetingId)}/session`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/meetings/${encodeURIComponent(meetingId)}/session`;
}

export function openSessionSocket(meetingId: string): SessionSocket {
  const ws = new WebSocket(_wsUrl(meetingId));

  const wrapper: SessionSocket = {
    onOpen: null,
    onMessage: null,
    onError: null,
    onClose: null,
    send(message) {
      ws.send(JSON.stringify(message));
    },
    close() {
      ws.close();
    },
  };

  ws.onopen = () => wrapper.onOpen?.();

  ws.onmessage = (ev: MessageEvent) => {
    let parsed: SessionMessage | null = null;
    try {
      parsed = JSON.parse(ev.data) as SessionMessage;
    } catch (err) {
      wrapper.onError?.(err);
      return;
    }
    wrapper.onMessage?.(parsed);
  };

  ws.onerror = (ev) => wrapper.onError?.(ev);
  ws.onclose = (ev) => wrapper.onClose?.(ev);

  return wrapper;
}
