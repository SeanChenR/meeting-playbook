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
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import {
  openSessionSocket,
  type SessionMessage,
  type SessionSocket,
  type Stream,
  type TranscriptChunkMessage,
} from "../lib/session-ws";

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

export type SessionState =
  | { phase: "idle" }
  | { phase: "connecting" }
  | {
      phase: "in_progress";
      chunks: TranscriptChunkMessage[];
      silenceSinceByStream: SilenceSinceByStream;
      streamStatus: StreamStatusByStream;
    }
  | {
      // After the user clicks End: server is still draining the queued
      // audio chunks. Late transcript_chunk frames continue to arrive.
      phase: "ending";
      chunks: TranscriptChunkMessage[];
      streamStatus: StreamStatusByStream;
    }
  | { phase: "ended"; chunks: TranscriptChunkMessage[] }
  | {
      phase: "error";
      errorCode: string;
      message: string;
      chunks: TranscriptChunkMessage[];
    };

type Action =
  | { type: "START" }
  | { type: "END_REQUESTED" }
  | { type: "WS_MESSAGE"; payload: SessionMessage }
  | { type: "UNEXPECTED_CLOSE" }
  | { type: "RETRY_FAILED" }
  | { type: "RESET" };

const initialState: SessionState = { phase: "idle" };

function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "START":
      return { phase: "connecting" };
    case "END_REQUESTED":
      if (state.phase === "in_progress") {
        return { phase: "ending", chunks: state.chunks, streamStatus: state.streamStatus };
      }
      return state;
    case "WS_MESSAGE": {
      const msg = action.payload;
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
        };
      }
      if (msg.type === "meeting_started") {
        return {
          phase: "in_progress",
          chunks: [],
          silenceSinceByStream: { ...initialSilenceSince },
          streamStatus: { ...initialStreamStatus },
        };
      }
      if (msg.type === "transcript_chunk") {
        if (state.phase === "in_progress") {
          // Receiving chunks for a stream means it is no longer silent.
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
        // A stream crashed mid-session. Mark it stopped; do NOT end the
        // session — the other stream keeps producing chunks. silence_warning
        // for the stopped stream is no longer meaningful, clear it.
        if (state.phase !== "in_progress" && state.phase !== "ending") return state;
        const next = {
          ...state,
          streamStatus: { ...state.streamStatus, [msg.stream]: "stopped" as StreamStatus },
        };
        if (state.phase === "in_progress") {
          return {
            ...next,
            silenceSinceByStream: {
              ...state.silenceSinceByStream,
              [msg.stream]: null,
            },
          };
        }
        return next;
      }
      if (msg.type === "meeting_ended") {
        if (state.phase !== "in_progress" && state.phase !== "ending") return state;
        return { phase: "ended", chunks: state.chunks };
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
}

export function useMeetingSession(meetingId: string): UseMeetingSessionResult {
  const [state, dispatch] = useReducer(reducer, initialState);
  const socketRef = useRef<SessionSocket | null>(null);
  const retryAttemptedRef = useRef<boolean>(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // True when WE close the socket (end() or unmount), so onClose can skip
  // the unexpected-close retry path.
  const intentionalCloseRef = useRef<boolean>(false);

  const wireSocket = useCallback(
    (sock: SessionSocket) => {
      sock.onMessage = (msg) => {
        dispatch({ type: "WS_MESSAGE", payload: msg });
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
    // Browser WebSocket.send before OPEN throws InvalidStateError silently
    // inside microtasks. Defer the start_meeting frame to onOpen so it
    // always lands.
    sock.onOpen = () => {
      sock.send({ type: "start_meeting", meeting_id: meetingId });
    };
  }, [meetingId, wireSocket]);

  const end = useCallback(() => {
    if (!socketRef.current) return;
    dispatch({ type: "END_REQUESTED" });
    socketRef.current.send({ type: "end_meeting", meeting_id: meetingId });
  }, [meetingId]);

  // Unmount cleanup: close the socket without sending end_meeting so the
  // router treats it as a client-disconnect end-of-session.
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

  return { state, start, end };
}
