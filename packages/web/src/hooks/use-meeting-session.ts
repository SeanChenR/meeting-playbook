/**
 * useMeetingSession — owns the meeting WebSocket lifecycle + reducer state.
 *
 * Per spec meeting-session ADDED requirement "useMeetingSession hook owns
 * the WebSocket lifecycle and reducer state":
 * - State machine: idle → connecting → in_progress → ended | error
 * - WS instance held in a ref; reducer dispatches by inbound message type
 * - On unexpected close during `in_progress`: one reconnect attempt with
 *   1-second backoff, then transition to `error` if reconnect also fails
 * - On unmount: closes WS without sending end_meeting (router treats
 *   client-close as end-of-session per design)
 *
 * Slice-9 changes: reducer's advisor slice replaced with chat-history shape
 * (`messages: ChatMessage[]` + `inFlight` snapshot). Persisted history is
 * hydrated via React Query GET; in-flight token streams are local state
 * only and clear on `advice_done` (the React Query cache is then
 * invalidated by the route, which refetches and brings the new pair in).
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ChatMessage } from "../lib/chat-api";
import {
  openSessionSocket,
  type RecordingMode,
  type SessionMessage,
  type SessionSocket,
  type Stream,
  type TranscriptChunkMessage,
} from "../lib/session-ws";

// Slice-27: recording mode default. Lives in module scope so the reset
// transition (`session ended → mode: "dual"`) reuses the same literal as
// `initialState` and the spec contract stays in one place.
const DEFAULT_RECORDING_MODE: RecordingMode = "dual";

// ─── State ─────────────────────────────────────────────────────────────────

export type SessionPhase = "idle" | "connecting" | "in_progress" | "ending" | "ended" | "error";

export type StreamStatus = "active" | "silence" | "stopped";

export type SilenceSinceByStream = Record<Stream, string | null>;
export type StreamStatusByStream = Record<Stream, StreamStatus>;

const initialStreamStatus: StreamStatusByStream = {
  me: "active",
  counterparty: "active",
};

const initialSilenceSince: SilenceSinceByStream = {
  me: null,
  counterparty: null,
};

// Slice-9: advisor slice = persisted chat history + at-most-one in-flight
// advice. Persisted messages come from the GET /chat_messages hydration;
// in-flight advice is local UI state only and disappears on done/failed.
export type InFlightStatus = "streaming" | "failed";

export interface InFlightAdvice {
  requestId: string;
  userContent: string; // what the user actually sent (chatbox content or default prompt)
  advisorTokens: string;
  status: InFlightStatus;
  // Source path so retry can pick the right WS frame to resend.
  source: "button" | "chatbox";
  error?: { code: string; message: string };
}

export interface AdvisorState {
  messages: ChatMessage[];
  inFlight: InFlightAdvice | null;
}

const initialAdvisor: AdvisorState = { messages: [], inFlight: null };

// Slice-27 D7: `mode` lives on every state variant so the UI can read it
// regardless of phase. The reducer initialises and resets to "dual" per D1.
export type SessionState =
  | { phase: "idle"; advisor: AdvisorState; mode: RecordingMode }
  | { phase: "connecting"; advisor: AdvisorState; mode: RecordingMode }
  | {
      phase: "in_progress";
      chunks: TranscriptChunkMessage[];
      silenceSinceByStream: SilenceSinceByStream;
      streamStatus: StreamStatusByStream;
      advisor: AdvisorState;
      mode: RecordingMode;
    }
  | {
      phase: "ending";
      chunks: TranscriptChunkMessage[];
      streamStatus: StreamStatusByStream;
      advisor: AdvisorState;
      mode: RecordingMode;
    }
  | {
      phase: "ended";
      chunks: TranscriptChunkMessage[];
      advisor: AdvisorState;
      mode: RecordingMode;
    }
  | {
      phase: "error";
      errorCode: string;
      message: string;
      chunks: TranscriptChunkMessage[];
      advisor: AdvisorState;
      mode: RecordingMode;
    };

type Action =
  | { type: "START" }
  | { type: "END_REQUESTED" }
  | { type: "WS_MESSAGE"; payload: SessionMessage }
  | { type: "HISTORY_LOADED"; messages: ChatMessage[] }
  | {
      type: "USER_MESSAGE_SENT";
      requestId: string;
      userContent: string;
      source: "button" | "chatbox";
    }
  | { type: "SET_MODE"; mode: RecordingMode }
  | { type: "UNEXPECTED_CLOSE" }
  | { type: "RETRY_FAILED" }
  | { type: "RESET" };

const initialState: SessionState = {
  phase: "idle",
  advisor: initialAdvisor,
  mode: DEFAULT_RECORDING_MODE,
};

function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "START":
      // Slice-27 D5: mode is locked at this point; carried through the
      // session lifecycle and read by `start()` for the start_meeting frame.
      return { phase: "connecting", advisor: state.advisor, mode: state.mode };
    case "END_REQUESTED":
      if (state.phase === "in_progress") {
        return {
          phase: "ending",
          chunks: state.chunks,
          streamStatus: state.streamStatus,
          advisor: state.advisor,
          mode: state.mode,
        };
      }
      return state;
    case "SET_MODE":
      // Slice-27 D5: mode is mutable ONLY in pre-session phases. While
      // `connecting` / `in_progress` / `ending` are live the WS already
      // owns the chosen mode; ignore the action so a stray UI click can't
      // desync the user-visible state from the wire contract.
      if (
        state.phase === "connecting" ||
        state.phase === "in_progress" ||
        state.phase === "ending"
      ) {
        return state;
      }
      return { ...state, mode: action.mode };
    case "HISTORY_LOADED":
      // Equality guard: if the same array reference (React Query stable
      // cache) lands here, return the same state object so React skips
      // the re-render and the route's useEffect doesn't loop.
      if (state.advisor.messages === action.messages) return state;
      return {
        ...state,
        advisor: { ...state.advisor, messages: action.messages },
      };
    case "USER_MESSAGE_SENT":
      // Set the in-flight advice. If something was already in-flight (e.g.
      // failed but not retried), it is replaced — the new send supersedes.
      return {
        ...state,
        advisor: {
          ...state.advisor,
          inFlight: {
            requestId: action.requestId,
            userContent: action.userContent,
            advisorTokens: "",
            status: "streaming",
            source: action.source,
          },
        },
      };
    case "WS_MESSAGE": {
      const msg = action.payload;
      if (msg.type === "advice_chunk") {
        // Only mutate if the chunk's request_id matches the current in-flight.
        const cur = state.advisor.inFlight;
        if (cur === null || cur.requestId !== msg.request_id) return state;
        return {
          ...state,
          advisor: {
            ...state.advisor,
            inFlight: { ...cur, advisorTokens: cur.advisorTokens + msg.token },
          },
        };
      }
      if (msg.type === "advice_done") {
        // Clear in-flight; the route invalidates the React Query cache and
        // the refetch will bring the persisted pair into `messages`.
        const cur = state.advisor.inFlight;
        if (cur === null || cur.requestId !== msg.request_id) return state;
        return {
          ...state,
          advisor: { ...state.advisor, inFlight: null },
        };
      }
      if (msg.type === "advisor_failed") {
        const cur = state.advisor.inFlight;
        if (cur === null || cur.requestId !== msg.request_id) return state;
        return {
          ...state,
          advisor: {
            ...state.advisor,
            inFlight: {
              ...cur,
              status: "failed",
              error: { code: msg.error_code, message: msg.message },
            },
          },
        };
      }
      if (msg.type === "error") {
        const chunks =
          state.phase === "in_progress" ||
          state.phase === "ending" ||
          state.phase === "ended" ||
          state.phase === "error"
            ? state.chunks
            : [];
        return {
          phase: "error",
          errorCode: msg.error_code,
          message: msg.message,
          chunks,
          advisor: state.advisor,
          // Preserve the mode that triggered the error so the UI can show
          // which path failed; the next `RESET` snaps it back to default.
          mode: state.mode,
        };
      }
      if (msg.type === "meeting_started") {
        return {
          phase: "in_progress",
          chunks: [],
          silenceSinceByStream: { ...initialSilenceSince },
          streamStatus: { ...initialStreamStatus },
          advisor: state.advisor,
          mode: state.mode,
        };
      }
      if (msg.type === "transcript_chunk") {
        if (state.phase === "in_progress") {
          return {
            ...state,
            chunks: [...state.chunks, msg],
            silenceSinceByStream: { ...state.silenceSinceByStream, [msg.speaker]: null },
            streamStatus:
              state.streamStatus[msg.speaker] === "stopped"
                ? state.streamStatus
                : { ...state.streamStatus, [msg.speaker]: "active" },
          };
        }
        if (state.phase === "ending") {
          return { ...state, chunks: [...state.chunks, msg] };
        }
        return state;
      }
      if (msg.type === "silence_warning") {
        if (state.phase !== "in_progress") return state;
        return {
          ...state,
          silenceSinceByStream: { ...state.silenceSinceByStream, [msg.stream]: msg.since },
          streamStatus:
            state.streamStatus[msg.stream] === "stopped"
              ? state.streamStatus
              : { ...state.streamStatus, [msg.stream]: "silence" },
        };
      }
      if (msg.type === "stream_stopped") {
        if (state.phase === "in_progress") {
          return {
            ...state,
            streamStatus: { ...state.streamStatus, [msg.stream]: "stopped" as StreamStatus },
            silenceSinceByStream: { ...state.silenceSinceByStream, [msg.stream]: null },
          };
        }
        if (state.phase === "ending") {
          return {
            ...state,
            streamStatus: { ...state.streamStatus, [msg.stream]: "stopped" as StreamStatus },
          };
        }
        return state;
      }
      if (msg.type === "meeting_ended") {
        if (state.phase !== "in_progress" && state.phase !== "ending") return state;
        // Slice-27 D1 + D7: session lifecycle ends → reset mode to dual
        // so a subsequent session on the same hook instance starts from
        // the documented default. Avoids the "last time single, this time
        // I forgot" failure mode without persisting state.
        return {
          phase: "ended",
          chunks: state.chunks,
          advisor: state.advisor,
          mode: DEFAULT_RECORDING_MODE,
        };
      }
      return state;
    }
    case "UNEXPECTED_CLOSE":
      return state;
    case "RETRY_FAILED": {
      const chunks =
        state.phase === "in_progress" ||
        state.phase === "ending" ||
        state.phase === "ended" ||
        state.phase === "error"
          ? state.chunks
          : [];
      return {
        phase: "error",
        errorCode: "session.connection_lost",
        message: "WebSocket disconnected; retry attempt also failed.",
        chunks,
        advisor: state.advisor,
        mode: state.mode,
      };
    }
    case "RESET":
      return initialState;
  }
}

// ─── Hook ──────────────────────────────────────────────────────────────────

export interface UseMeetingSessionResult {
  state: SessionState;
  start: () => void;
  end: () => void;
  requestAdvice: () => void;
  sendChatMessage: (content: string) => void;
  loadHistory: (messages: ChatMessage[]) => void;
  /** Slice-27: set the recording mode prior to `start()`. Ignored once the
   * session is `connecting` / `in_progress` / `ending` (mode is immutable
   * after the WS `start_meeting` frame is sent, per spec ADDED requirement
   * "...Once `start_meeting` has been accepted the mode SHALL be immutable
   * for the lifetime of that WebSocket"). */
  setMode: (mode: RecordingMode) => void;
  /** Notification hook: invoked after the reducer processes `advice_done`.
   * The route uses this to invalidate the React Query cache so the persisted
   * pair lands in `messages`. Slice-9 design.md Decision 6. */
  onAdviceDone: ((requestId: string) => void) | null;
}

function _generateRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useMeetingSession(meetingId: string): UseMeetingSessionResult {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { i18n, t } = useTranslation();
  const socketRef = useRef<SessionSocket | null>(null);
  const retryAttemptedRef = useRef<boolean>(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef<boolean>(false);
  // Slice-27: keep the latest mode in a ref so the stable `start` callback
  // can read it without re-binding (and without going stale). The reducer
  // is the source of truth; the ref is just a cheap read for the WS frame.
  const modeRef = useRef<RecordingMode>(state.mode);
  modeRef.current = state.mode;
  // Slice-9: route registers a callback here so the reducer can notify
  // when a stream completes (so React Query can invalidate the chat_messages
  // cache and refetch). Stored in a ref so the route can update it without
  // re-wiring the WS.
  const onAdviceDoneRef = useRef<((requestId: string) => void) | null>(null);

  const wireSocket = useCallback(
    (sock: SessionSocket) => {
      sock.onMessage = (msg) => {
        dispatch({ type: "WS_MESSAGE", payload: msg });
        // Notify the route on advice_done so it can invalidate the React
        // Query cache. Done AFTER dispatch so reducer state reflects the
        // cleared in-flight before the route reads it.
        if (msg.type === "advice_done" && onAdviceDoneRef.current) {
          onAdviceDoneRef.current(msg.request_id);
        }
        if (msg.type === "error" || msg.type === "meeting_ended") {
          intentionalCloseRef.current = true;
          sock.close();
        }
      };
      sock.onClose = (ev) => {
        if (intentionalCloseRef.current) {
          intentionalCloseRef.current = false;
          return;
        }
        const wasClean = ev?.wasClean === true;
        if (wasClean) return;
        if (retryAttemptedRef.current) {
          dispatch({ type: "RETRY_FAILED" });
          return;
        }
        retryAttemptedRef.current = true;
        retryTimerRef.current = setTimeout(() => {
          retryTimerRef.current = null;
          const retried = openSessionSocket(meetingId);
          socketRef.current = retried;
          wireSocket(retried);
        }, 1000);
      };
    },
    [meetingId],
  );

  const start = useCallback(() => {
    if (socketRef.current) return;
    retryAttemptedRef.current = false;
    dispatch({ type: "START" });
    const sock = openSessionSocket(meetingId);
    socketRef.current = sock;
    wireSocket(sock);
    sock.onOpen = () => {
      // Slice-27: include the user-selected recording mode in the
      // start_meeting frame so the backend can route the pre-flight.
      sock.send({
        type: "start_meeting",
        meeting_id: meetingId,
        mode: modeRef.current,
      });
    };
  }, [meetingId, wireSocket]);

  const setMode = useCallback((mode: RecordingMode) => {
    dispatch({ type: "SET_MODE", mode });
  }, []);

  const end = useCallback(() => {
    if (!socketRef.current) return;
    dispatch({ type: "END_REQUESTED" });
    socketRef.current.send({ type: "end_meeting", meeting_id: meetingId });
  }, [meetingId]);

  const _coerceLocale = useCallback((): "zh-TW" | "en" => {
    return i18n.language?.toLowerCase().startsWith("en") ? "en" : "zh-TW";
  }, [i18n]);

  const requestAdvice = useCallback(() => {
    if (!socketRef.current) return;
    const requestId = _generateRequestId();
    const locale = _coerceLocale();
    // Mirror the backend's locale-default prompt so the local in-flight
    // bubble shows the same text the server will eventually persist.
    const userContent = t("meetings.advisor.defaultPromptText");
    dispatch({
      type: "USER_MESSAGE_SENT",
      requestId,
      userContent,
      source: "button",
    });
    socketRef.current.send({
      type: "request_advice",
      request_id: requestId,
      locale,
    });
  }, [_coerceLocale, t]);

  const sendChatMessage = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || !socketRef.current) return;
      const requestId = _generateRequestId();
      const locale = _coerceLocale();
      dispatch({
        type: "USER_MESSAGE_SENT",
        requestId,
        userContent: trimmed,
        source: "chatbox",
      });
      socketRef.current.send({
        type: "chat_message",
        request_id: requestId,
        content: trimmed,
        locale,
      });
    },
    [_coerceLocale],
  );

  const loadHistory = useCallback((messages: ChatMessage[]) => {
    dispatch({ type: "HISTORY_LOADED", messages });
  }, []);

  // Unmount cleanup
  useEffect(() => {
    return () => {
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      if (socketRef.current) {
        intentionalCloseRef.current = true;
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, []);

  // Expose `onAdviceDone` as a getter/setter via the result object so the
  // route can register its callback. We return a stable shape: assigning to
  // `result.onAdviceDone = fn` writes to the ref.
  const result: UseMeetingSessionResult = {
    state,
    start,
    end,
    requestAdvice,
    sendChatMessage,
    loadHistory,
    setMode,
    get onAdviceDone() {
      return onAdviceDoneRef.current;
    },
    set onAdviceDone(fn: ((requestId: string) => void) | null) {
      onAdviceDoneRef.current = fn;
    },
  };
  return result;
}
