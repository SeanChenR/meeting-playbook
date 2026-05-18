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

export type Stream = "me" | "counterparty";

export type TranscriptChunkMessage = {
  type: "transcript_chunk";
  /**
   * DB row id (`tc_xxx`) when the chunk came from REST replay
   * (`rowToMessage`) or when the WebSocket frame carried one. Absent
   * for live-capture frames that haven't been persisted yet — slice-16
   * chunk edit / play actions therefore SHOULD only mount on chunks
   * with a real id.
   */
  id?: string;
  meeting_id: string;
  speaker: Stream;
  text: string;
  started_at: string;
  ended_at: string;
  asr_provider_used: string;
  confidence: number | null;
};

export type SilenceWarningMessage = {
  type: "silence_warning";
  meeting_id: string;
  stream: Stream;
  since: string;
};

// Slice-7: emitted when one capture stream fails mid-session.
// The other stream continues; the WebSocket stays open until both stop.
export type StreamStoppedMessage = {
  type: "stream_stopped";
  meeting_id: string;
  stream: Stream;
  reason: string;
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

// Slice-8: TacticalAdvisor streaming frames. Each is correlated with the
// originating `request_advice.request_id` so the UI can keep multiple
// historical advice cards distinct.
export type AdviceChunkMessage = {
  type: "advice_chunk";
  request_id: string;
  token: string;
};

export type AdviceDoneMessage = {
  type: "advice_done";
  request_id: string;
};

export type AdvisorFailedMessage = {
  type: "advisor_failed";
  request_id: string;
  error_code: string;
  message: string;
};

export type SessionMessage =
  | MeetingStartedMessage
  | TranscriptChunkMessage
  | SilenceWarningMessage
  | StreamStoppedMessage
  | MeetingEndedMessage
  | ErrorMessage
  | AdviceChunkMessage
  | AdviceDoneMessage
  | AdvisorFailedMessage;

// ─── Client → server message types ─────────────────────────────────────────

/**
 * Slice-27 (single-channel-recording-entry): recording mode chooses the
 * capture pipeline before the session opens.
 *
 * - `"dual"`  → capture mic (`me`) + BlackHole (`counterparty`). Pre-flight
 *               requires BlackHole; backend default for missing field.
 * - `"single"` → capture mic only. Pre-flight skips the BlackHole check.
 *
 * Mirrors `RecordingMode` in
 * `packages/backend/meeting_playbook/sessions/messages.py`. Keep both in
 * lockstep — the spec Example table is the contract.
 */
export type RecordingMode = "dual" | "single";

export type StartMeetingMessage = {
  type: "start_meeting";
  meeting_id: string;
  mode: RecordingMode;
};
export type EndMeetingMessage = { type: "end_meeting"; meeting_id: string };
// Slice-8: button-only path leaves user_question undefined; slice-9 chatbox
// will populate it with the user's typed prompt.
export type RequestAdviceMessage = {
  type: "request_advice";
  request_id: string;
  locale: "zh-TW" | "en";
  user_question?: string | null;
};

// Slice-9: chatbox follow-up. `content` is the user's typed question;
// `request_id` is a client-generated UUID used for correlating the response
// back to the right card.
export type ChatMessageRequestMessage = {
  type: "chat_message";
  request_id: string;
  content: string;
  locale: "zh-TW" | "en";
};

export type ClientMessage =
  | StartMeetingMessage
  | EndMeetingMessage
  | RequestAdviceMessage
  | ChatMessageRequestMessage;

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
