/**
 * session-ws — thin async wrapper around the meeting WebSocket.
 *
 * Per spec meeting-session ADDED requirement "useMeetingSession hook owns
 * the WebSocket lifecycle and reducer state" — this lib provides the
 * untyped wrapper that the hook drives.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { openSessionSocket, type SessionMessage } from "./session-ws";

// ─── Minimal MockWebSocket ─────────────────────────────────────────────────

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0; // CONNECTING
  sent: string[] = [];
  closed = false;
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
    this.closed = true;
    this.readyState = 3; // CLOSED
    this.onclose?.(new CloseEvent("close"));
  }

  // Test helpers
  simulateOpen(): void {
    this.readyState = 1; // OPEN
    this.onopen?.(new Event("open"));
  }
  simulateMessage(data: string): void {
    this.onmessage?.(new MessageEvent("message", { data }));
  }
}

const originalWS = globalThis.WebSocket;

afterEach(() => {
  globalThis.WebSocket = originalWS;
  MockWebSocket.instances = [];
});

function installMock(): typeof MockWebSocket {
  // @ts-expect-error: substituting WebSocket constructor
  globalThis.WebSocket = MockWebSocket;
  return MockWebSocket;
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe("openSessionSocket", () => {
  test("opens WebSocket against /api/meetings/{id}/session and exposes send/close/onMessage", () => {
    installMock();
    const sock = openSessionSocket("m_abc");

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0]?.url).toContain("/api/meetings/m_abc/session");
    expect(typeof sock.send).toBe("function");
    expect(typeof sock.close).toBe("function");
    expect("onMessage" in sock).toBe(true);
  });

  test("inbound JSON is parsed and dispatched to onMessage as a typed payload", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    const received: SessionMessage[] = [];
    sock.onMessage = (msg) => {
      received.push(msg);
    };

    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();
    ws.simulateMessage(JSON.stringify({ type: "meeting_started", meeting_id: "m_abc" }));

    expect(received).toHaveLength(1);
    expect(received[0]).toEqual({ type: "meeting_started", meeting_id: "m_abc" });
  });

  test("malformed JSON triggers onError callback (does NOT crash onMessage)", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    const onError = mock(() => {});
    const onMessage = mock(() => {});
    sock.onError = onError;
    sock.onMessage = onMessage;

    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();
    ws.simulateMessage("this is not json {{{ broken");

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onMessage).not.toHaveBeenCalled();
  });

  test("send() JSON-stringifies and writes to the underlying socket", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();

    sock.send({ type: "start_meeting", meeting_id: "m_abc" });
    sock.send({ type: "end_meeting", meeting_id: "m_abc" });

    expect(ws.sent).toEqual([
      JSON.stringify({ type: "start_meeting", meeting_id: "m_abc" }),
      JSON.stringify({ type: "end_meeting", meeting_id: "m_abc" }),
    ]);
  });

  test("close() closes the underlying socket", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    const ws = MockWebSocket.instances[0]!;
    sock.close();
    expect(ws.closed).toBe(true);
  });

  // ─── Slice 7 ─────────────────────────────────────────────────────

  test("parses stream_stopped frame into the discriminated union", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    let received: SessionMessage | null = null;
    sock.onMessage = (msg) => {
      received = msg;
    };
    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();
    ws.simulateMessage(
      JSON.stringify({
        type: "stream_stopped",
        meeting_id: "m_abc",
        stream: "counterparty",
        reason: "BlackHole driver crashed",
      }),
    );

    expect(received).not.toBeNull();
    const msg = received!;
    expect(msg.type).toBe("stream_stopped");
    if (msg.type === "stream_stopped") {
      expect(msg.stream).toBe("counterparty");
      expect(msg.reason).toBe("BlackHole driver crashed");
    }
  });

  // ─── Slice 9: chatbox client frame ────────────────────────────────

  test("send({type: 'chat_message', ...}) writes the JSON payload to the underlying WS", () => {
    installMock();
    const sock = openSessionSocket("m_chat");
    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();

    sock.send({
      type: "chat_message",
      request_id: "r_x",
      content: "對方剛說 X 怎麼回",
      locale: "zh-TW",
    });

    expect(ws.sent).toHaveLength(1);
    const parsed = JSON.parse(ws.sent[0]!);
    expect(parsed).toEqual({
      type: "chat_message",
      request_id: "r_x",
      content: "對方剛說 X 怎麼回",
      locale: "zh-TW",
    });
  });

  // ─── Slice 8: TacticalAdvisor frames ──────────────────────────────

  test("parses advice_chunk / advice_done / advisor_failed into the discriminated union", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    const received: SessionMessage[] = [];
    sock.onMessage = (msg) => {
      received.push(msg);
    };
    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();

    ws.simulateMessage(
      JSON.stringify({ type: "advice_chunk", request_id: "req_1", token: "alpha" }),
    );
    ws.simulateMessage(JSON.stringify({ type: "advice_done", request_id: "req_1" }));
    ws.simulateMessage(
      JSON.stringify({
        type: "advisor_failed",
        request_id: "req_2",
        error_code: "advisor.timeout",
        message: "Vertex stream timed out after 15s",
      }),
    );

    expect(received).toHaveLength(3);
    expect(received[0]!.type).toBe("advice_chunk");
    if (received[0]!.type === "advice_chunk") {
      expect(received[0]!.request_id).toBe("req_1");
      expect(received[0]!.token).toBe("alpha");
    }
    expect(received[1]!.type).toBe("advice_done");
    if (received[1]!.type === "advice_done") {
      expect(received[1]!.request_id).toBe("req_1");
    }
    expect(received[2]!.type).toBe("advisor_failed");
    if (received[2]!.type === "advisor_failed") {
      expect(received[2]!.error_code).toBe("advisor.timeout");
      expect(received[2]!.message).toContain("timed out");
    }
  });

  test("parses silence_warning frame including stream field", () => {
    installMock();
    const sock = openSessionSocket("m_abc");
    let received: SessionMessage | null = null;
    sock.onMessage = (msg) => {
      received = msg;
    };
    const ws = MockWebSocket.instances[0]!;
    ws.simulateOpen();
    ws.simulateMessage(
      JSON.stringify({
        type: "silence_warning",
        meeting_id: "m_abc",
        stream: "me",
        since: "2026-05-10T10:00:00+00:00",
      }),
    );

    expect(received).not.toBeNull();
    const msg = received!;
    expect(msg.type).toBe("silence_warning");
    if (msg.type === "silence_warning") {
      expect(msg.stream).toBe("me");
    }
  });
});
