/**
 * useMeetingSession reducer + WS lifecycle tests.
 *
 * Per spec meeting-session ADDED requirement "useMeetingSession hook owns
 * the WebSocket lifecycle and reducer state" — every reducer transition is
 * covered with mocked WebSocket message sequences.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";

// ─── MockWebSocket (shared across tests) ───────────────────────────────────

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0;
  sent: string[] = [];
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }

  simulateOpen(): void {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }
  simulateMessage(payload: object): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }
  simulateUnexpectedClose(): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { wasClean: false } as CloseEventInit));
  }
}

const originalWS = globalThis.WebSocket;

beforeEach(() => {
  // @ts-expect-error: substituting WebSocket constructor
  globalThis.WebSocket = MockWebSocket;
  MockWebSocket.instances = [];
});

afterEach(() => {
  globalThis.WebSocket = originalWS;
  cleanup();
});

import { useMeetingSession } from "./use-meeting-session";

// ─── Tests ─────────────────────────────────────────────────────────────────

describe("useMeetingSession", () => {
  test("initial state is { phase: 'idle' }", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    expect(result.current.state.phase).toBe("idle");
  });

  test("start() opens WS and state becomes connecting", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(result.current.state.phase).toBe("connecting");
  });

  test("on meeting_started → phase in_progress with empty chunks and null silenceSince", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      // After open, send start_meeting; reducer doesn't care, just the inbound.
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    expect(result.current.state.phase).toBe("in_progress");
    if (result.current.state.phase === "in_progress") {
      expect(result.current.state.chunks).toEqual([]);
      expect(result.current.state.silenceSinceByStream).toEqual({
        me: null,
        counterparty: null,
      });
      expect(result.current.state.streamStatus).toEqual({
        me: "active",
        counterparty: "active",
      });
    }
  });

  test("transcript_chunk appends to chunks in arrival order", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
      ws.simulateMessage({
        type: "transcript_chunk",
        meeting_id: "m_a",
        speaker: "me",
        text: "first",
        started_at: "t1",
        ended_at: "t2",
        asr_provider_used: "whisper",
        confidence: 0.9,
      });
      ws.simulateMessage({
        type: "transcript_chunk",
        meeting_id: "m_a",
        speaker: "me",
        text: "second",
        started_at: "t3",
        ended_at: "t4",
        asr_provider_used: "whisper",
        confidence: null,
      });
    });
    if (result.current.state.phase === "in_progress") {
      expect(result.current.state.chunks).toHaveLength(2);
      expect(result.current.state.chunks[0]?.text).toBe("first");
      expect(result.current.state.chunks[1]?.text).toBe("second");
    } else {
      throw new Error(`expected in_progress, got ${result.current.state.phase}`);
    }
  });

  test("silence_warning per stream populates only that stream's silenceSince", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
      ws.simulateMessage({
        type: "silence_warning",
        meeting_id: "m_a",
        stream: "counterparty",
        since: "2026-05-09T10:00:00Z",
      });
    });
    if (result.current.state.phase === "in_progress") {
      expect(result.current.state.silenceSinceByStream).toEqual({
        me: null,
        counterparty: "2026-05-09T10:00:00Z",
      });
      expect(result.current.state.streamStatus).toEqual({
        me: "active",
        counterparty: "silence",
      });
    } else {
      throw new Error("expected in_progress");
    }
  });

  test("stream_stopped marks one stream stopped without ending the session", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
      ws.simulateMessage({
        type: "stream_stopped",
        meeting_id: "m_a",
        stream: "counterparty",
        reason: "BlackHole driver crashed",
      });
    });
    if (result.current.state.phase === "in_progress") {
      expect(result.current.state.streamStatus).toEqual({
        me: "active",
        counterparty: "stopped",
      });
    } else {
      throw new Error(
        `expected in_progress (other stream still alive), got ${result.current.state.phase}`,
      );
    }
  });

  test("meeting_ended → phase ended (chunks preserved)", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
      ws.simulateMessage({
        type: "transcript_chunk",
        meeting_id: "m_a",
        speaker: "me",
        text: "the only one",
        started_at: "t1",
        ended_at: "t2",
        asr_provider_used: "whisper",
        confidence: null,
      });
      ws.simulateMessage({ type: "meeting_ended", meeting_id: "m_a" });
    });
    expect(result.current.state.phase).toBe("ended");
    if (result.current.state.phase === "ended") {
      expect(result.current.state.chunks).toHaveLength(1);
    }
  });

  test("error message → phase error with errorCode and WS closed", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
      ws.simulateMessage({
        type: "error",
        error_code: "session.persist_failed",
        message: "DB down",
      });
    });
    expect(result.current.state.phase).toBe("error");
    if (result.current.state.phase === "error") {
      expect(result.current.state.errorCode).toBe("session.persist_failed");
    }
    expect(ws.readyState).toBe(3);
  });

  test("end() sends end_meeting message", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.end();
    });
    const lastSent = ws.sent[ws.sent.length - 1] ?? "";
    expect(JSON.parse(lastSent)).toEqual({
      type: "end_meeting",
      meeting_id: "m_a",
    });
  });

  // ─── Slice 9: chat history hydration + chatbox lifecycle ──────────

  test("HISTORY_LOADED replaces messages on the advisor slice", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    const sample = [
      {
        id: "cm_1",
        meeting_id: "m_a",
        role: "user" as const,
        content: "Q1",
        created_at: "2026-05-10T10:00:00Z",
      },
      {
        id: "cm_2",
        meeting_id: "m_a",
        role: "advisor" as const,
        content: "A1",
        created_at: "2026-05-10T10:00:01Z",
      },
      {
        id: "cm_3",
        meeting_id: "m_a",
        role: "user" as const,
        content: "Q2",
        created_at: "2026-05-10T10:01:00Z",
      },
    ];
    act(() => {
      result.current.loadHistory(sample);
    });
    expect(result.current.state.advisor.messages).toHaveLength(3);
    expect(result.current.state.advisor.messages[1]!.content).toBe("A1");
  });

  test("sendChatMessage sends a chat_message frame with a uuid request_id and locale", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.sendChatMessage("如果他繼續砍價呢");
    });
    const sent = ws.sent
      .map(
        (s) =>
          JSON.parse(s) as { type: string; request_id?: string; content?: string; locale?: string },
      )
      .find((m) => m.type === "chat_message");
    expect(sent).toBeDefined();
    expect(sent!.content).toBe("如果他繼續砍價呢");
    expect(typeof sent!.request_id).toBe("string");
    expect(sent!.request_id!.length).toBeGreaterThan(0);
    expect(["zh-TW", "en"]).toContain(sent!.locale!);
  });

  test("advice_chunk × 3 appends to inFlight.advisorTokens (concatenation)", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.sendChatMessage("Q");
    });
    const sent = ws.sent
      .map((s) => JSON.parse(s) as { type: string; request_id?: string })
      .find((m) => m.type === "chat_message")!;
    const requestId = sent.request_id!;

    act(() => {
      ws.simulateMessage({ type: "advice_chunk", request_id: requestId, token: "a" });
      ws.simulateMessage({ type: "advice_chunk", request_id: requestId, token: "b" });
      ws.simulateMessage({ type: "advice_chunk", request_id: requestId, token: "c" });
    });

    expect(result.current.state.advisor.inFlight).not.toBeNull();
    expect(result.current.state.advisor.inFlight!.advisorTokens).toBe("abc");
    expect(result.current.state.advisor.inFlight!.status).toBe("streaming");
    expect(result.current.state.advisor.inFlight!.userContent).toBe("Q");
  });

  test("advice_done clears inFlight (route is responsible for refetching history)", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.sendChatMessage("Q");
    });
    const sent = ws.sent
      .map((s) => JSON.parse(s) as { type: string; request_id?: string })
      .find((m) => m.type === "chat_message")!;
    const requestId = sent.request_id!;

    act(() => {
      ws.simulateMessage({ type: "advice_chunk", request_id: requestId, token: "ok" });
      ws.simulateMessage({ type: "advice_done", request_id: requestId });
    });

    expect(result.current.state.advisor.inFlight).toBeNull();
  });

  test("advisor_failed sets inFlight.status='failed' with the error code", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.sendChatMessage("Q");
    });
    const sent = ws.sent
      .map((s) => JSON.parse(s) as { type: string; request_id?: string })
      .find((m) => m.type === "chat_message")!;
    const requestId = sent.request_id!;

    act(() => {
      ws.simulateMessage({
        type: "advisor_failed",
        request_id: requestId,
        error_code: "advisor.timeout",
        message: "Vertex stream timed out after 15s",
      });
    });

    expect(result.current.state.advisor.inFlight).not.toBeNull();
    expect(result.current.state.advisor.inFlight!.status).toBe("failed");
    expect(result.current.state.advisor.inFlight!.error?.code).toBe("advisor.timeout");
    // userContent preserved so the UI can offer a retry that resends the same message.
    expect(result.current.state.advisor.inFlight!.userContent).toBe("Q");
  });

  test("requestAdvice (button path) sends request_advice frame and sets inFlight with default prompt as userContent", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.requestAdvice();
    });
    const sent = ws.sent
      .map((s) => JSON.parse(s) as { type: string })
      .find((m) => m.type === "request_advice");
    expect(sent).toBeDefined();
    // userContent is the i18n default prompt (zh-TW): 「請給出戰術建議。」
    expect(result.current.state.advisor.inFlight!.userContent).toBe("請給出戰術建議。");
    expect(result.current.state.advisor.inFlight!.source).toBe("button");
  });

  test("onAdviceDone callback fires when advice_done arrives", () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    let observedReqId: string | null = null;
    result.current.onAdviceDone = (rid: string) => {
      observedReqId = rid;
    };
    act(() => {
      result.current.start();
    });
    const ws = MockWebSocket.instances[0]!;
    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });
    act(() => {
      result.current.sendChatMessage("Q");
    });
    const sent = ws.sent
      .map((s) => JSON.parse(s) as { type: string; request_id?: string })
      .find((m) => m.type === "chat_message")!;
    const requestId = sent.request_id!;

    act(() => {
      ws.simulateMessage({ type: "advice_done", request_id: requestId });
    });

    expect(observedReqId).toBe(requestId);
  });

  test("unexpected close during in_progress triggers ONE retry then enters error", async () => {
    const { result } = renderHook(() => useMeetingSession("m_a"));
    act(() => {
      result.current.start();
    });
    const first = MockWebSocket.instances[0]!;
    act(() => {
      first.simulateOpen();
      first.simulateMessage({ type: "meeting_started", meeting_id: "m_a" });
    });

    // Server-side dies unexpectedly.
    await act(async () => {
      first.simulateUnexpectedClose();
    });

    // Hook reconnects exactly once. We do not advance fake timers — instead
    // the hook schedules a setTimeout(1000); we wait for the second instance.
    await waitFor(
      () => {
        expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
      },
      { timeout: 2000 },
    );

    const second = MockWebSocket.instances[1]!;
    // The retry attempt also dies unexpectedly → state goes to error.
    await act(async () => {
      second.simulateUnexpectedClose();
    });

    await waitFor(
      () => {
        expect(result.current.state.phase).toBe("error");
      },
      { timeout: 2000 },
    );
  });
});
