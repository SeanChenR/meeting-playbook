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
    expect(received!.type).toBe("stream_stopped");
    if (received!.type === "stream_stopped") {
      expect(received!.stream).toBe("counterparty");
      expect(received!.reason).toBe("BlackHole driver crashed");
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
    expect(received!.type).toBe("silence_warning");
    if (received!.type === "silence_warning") {
      expect(received!.stream).toBe("me");
    }
  });
});
