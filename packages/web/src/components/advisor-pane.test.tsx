/**
 * AdvisorPane — slice-9 chatbox surface tests.
 *
 * Per spec tactical-advisor MODIFIED requirement scenarios:
 * - History list renders persisted chat_message rows from React Query cache
 * - Get Advice button + chatbox controls visible only in_progress
 * - Send button disabled while streaming
 * - Failed in-flight surfaces a retry button bound to the right source path
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { AdvisorPane } from "./advisor-pane";
import type {
  AdvisorState,
  InFlightAdvice,
  SessionState,
  UseMeetingSessionResult,
} from "../hooks/use-meeting-session";
import type { ChatMessage } from "../lib/chat-api";

afterEach(cleanup);

function _stubSession(
  state: SessionState,
  overrides: Partial<UseMeetingSessionResult> = {},
): UseMeetingSessionResult {
  return {
    state,
    start: () => {},
    end: () => {},
    requestAdvice: () => {},
    sendChatMessage: () => {},
    loadHistory: () => {},
    onAdviceDone: null,
    ...overrides,
  };
}

function _advisor(
  messages: ChatMessage[] = [],
  inFlight: InFlightAdvice | null = null,
): AdvisorState {
  return { messages, inFlight };
}

function _idleState(advisor: AdvisorState = _advisor()): SessionState {
  return { phase: "idle", advisor };
}

function _inProgressState(advisor: AdvisorState = _advisor()): SessionState {
  return {
    phase: "in_progress",
    chunks: [],
    silenceSinceByStream: { me: null, counterparty: null },
    streamStatus: { me: "active", counterparty: "active" },
    advisor,
  };
}

function _endedState(advisor: AdvisorState = _advisor()): SessionState {
  return { phase: "ended", chunks: [], advisor };
}

const _MSG = (id: string, role: "user" | "advisor", content: string): ChatMessage => ({
  id,
  meeting_id: "m_x",
  role,
  content,
  created_at: "2026-05-10T10:00:00Z",
});

describe("AdvisorPane", () => {
  test("renders persisted chat history bubbles when state has messages", () => {
    const messages = [
      _MSG("cm_1", "user", "Q1"),
      _MSG("cm_2", "advisor", "A1"),
      _MSG("cm_3", "user", "Q2"),
      _MSG("cm_4", "advisor", "A2"),
    ];
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor(messages)))}
        meDisplayName="Sean"
      />,
    );
    const bubbles = screen.getAllByTestId("chat-bubble");
    expect(bubbles).toHaveLength(4);
    expect(bubbles[0]!.getAttribute("data-role")).toBe("user");
    expect(bubbles[1]!.getAttribute("data-role")).toBe("advisor");
  });

  test("phase=idle with no history → empty state visible, button hidden, chatbox visible but disabled", () => {
    render(<AdvisorPane session={_stubSession(_idleState())} meDisplayName="Sean" />);
    expect(screen.queryByTestId("advisor-pane-empty")).not.toBeNull();
    expect(screen.queryByTestId("get-advice-button")).toBeNull();
    // Claude-design alignment: ChatInput stays mounted across session states
    // so users always see the affordance — just disabled when offline.
    const textarea = screen.queryByTestId("chat-input-textarea") as HTMLTextAreaElement | null;
    expect(textarea).not.toBeNull();
    expect(textarea!.disabled).toBe(true);
    const sendBtn = screen.queryByTestId("chat-input-send") as HTMLButtonElement | null;
    expect(sendBtn).not.toBeNull();
    expect(sendBtn!.disabled).toBe(true);
  });

  test("phase=in_progress with no history → empty state hidden, button + chatbox visible", () => {
    render(<AdvisorPane session={_stubSession(_inProgressState())} meDisplayName="Sean" />);
    // In-progress + zero messages: empty state suppressed; controls show.
    expect(screen.queryByTestId("get-advice-button")).not.toBeNull();
    expect(screen.queryByTestId("chat-input-textarea")).not.toBeNull();
    expect(screen.queryByTestId("chat-input-send")).not.toBeNull();
  });

  test("phase=ended with persisted history → bubbles visible, advice button hidden, chatbox disabled", () => {
    const messages = [_MSG("cm_1", "user", "Q1"), _MSG("cm_2", "advisor", "A1")];
    render(
      <AdvisorPane session={_stubSession(_endedState(_advisor(messages)))} meDisplayName="Sean" />,
    );
    expect(screen.getAllByTestId("chat-bubble")).toHaveLength(2);
    expect(screen.queryByTestId("get-advice-button")).toBeNull();
    const textarea = screen.queryByTestId("chat-input-textarea") as HTMLTextAreaElement | null;
    expect(textarea).not.toBeNull();
    expect(textarea!.disabled).toBe(true);
    const sendBtn = screen.queryByTestId("chat-input-send") as HTMLButtonElement | null;
    expect(sendBtn).not.toBeNull();
    expect(sendBtn!.disabled).toBe(true);
  });

  test("inFlight streaming → 2 virtual bubbles appended; advisor bubble shows accumulated tokens", () => {
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "X",
      advisorTokens: "abc",
      status: "streaming",
      source: "chatbox",
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)))}
        meDisplayName="Sean"
      />,
    );
    const bubbles = screen.getAllByTestId("chat-bubble");
    expect(bubbles).toHaveLength(2);
    expect(bubbles[0]!.getAttribute("data-role")).toBe("user");
    expect(bubbles[0]!.textContent).toContain("X");
    expect(bubbles[1]!.getAttribute("data-role")).toBe("advisor");
    expect(bubbles[1]!.textContent).toContain("abc");
  });

  test("inFlight streaming with empty tokens → advisor bubble shows the localised 'thinking' text", () => {
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "X",
      advisorTokens: "",
      status: "streaming",
      source: "chatbox",
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)))}
        meDisplayName="Sean"
      />,
    );
    const bubbles = screen.getAllByTestId("chat-bubble");
    // zh-TW default: "思考中…"
    expect(bubbles[1]!.textContent).toContain("思考中");
  });

  test("Send button is disabled while inFlight is streaming", () => {
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "X",
      advisorTokens: "...",
      status: "streaming",
      source: "chatbox",
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)))}
        meDisplayName="Sean"
      />,
    );
    const send = screen.getByTestId("chat-input-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    const adv = screen.getByTestId("get-advice-button") as HTMLButtonElement;
    expect(adv.disabled).toBe(true);
  });

  test("Failed in-flight (chatbox source) renders Retry → calls sendChatMessage with original userContent", () => {
    const sendChatMessage = mock<(content: string) => void>(() => {});
    const requestAdvice = mock(() => {});
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "如果他繼續砍價",
      advisorTokens: "",
      status: "failed",
      source: "chatbox",
      error: { code: "advisor.timeout", message: "Vertex stream timed out after 15s" },
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)), {
          sendChatMessage,
          requestAdvice,
        })}
        meDisplayName="Sean"
      />,
    );
    fireEvent.click(screen.getByTestId("advice-retry-button"));
    expect(sendChatMessage).toHaveBeenCalledTimes(1);
    expect(sendChatMessage.mock.calls[0]![0]).toBe("如果他繼續砍價");
    expect(requestAdvice).not.toHaveBeenCalled();
    // Failed advisor bubble shows the localised error.
    const bubbles = screen.getAllByTestId("chat-bubble");
    expect(bubbles[1]!.textContent).toContain("逾時");
  });

  test("Failed in-flight (button source) renders Retry → calls requestAdvice", () => {
    const sendChatMessage = mock<(content: string) => void>(() => {});
    const requestAdvice = mock(() => {});
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "請給出戰術建議。",
      advisorTokens: "",
      status: "failed",
      source: "button",
      error: { code: "advisor.unknown", message: "boom" },
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)), {
          sendChatMessage,
          requestAdvice,
        })}
        meDisplayName="Sean"
      />,
    );
    fireEvent.click(screen.getByTestId("advice-retry-button"));
    expect(requestAdvice).toHaveBeenCalledTimes(1);
    expect(sendChatMessage).not.toHaveBeenCalled();
  });

  test("Get Advice button calls session.requestAdvice when clicked", () => {
    const requestAdvice = mock(() => {});
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(), { requestAdvice })}
        meDisplayName="Sean"
      />,
    );
    fireEvent.click(screen.getByTestId("get-advice-button"));
    expect(requestAdvice).toHaveBeenCalledTimes(1);
  });

  test("Sending a chat message via ChatInput Send calls session.sendChatMessage", () => {
    const sendChatMessage = mock<(content: string) => void>(() => {});
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(), { sendChatMessage })}
        meDisplayName="Sean"
      />,
    );
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "對方剛說 X" } });
    fireEvent.click(screen.getByTestId("chat-input-send"));
    expect(sendChatMessage).toHaveBeenCalledTimes(1);
    expect(sendChatMessage.mock.calls[0]![0]).toBe("對方剛說 X");
  });

  // ─── Phase 6 task 6.3 — ChatBubble + suggestion chips ───────────────

  test("(6.3a) user ChatBubble is right-aligned with --color-primary background", () => {
    const messages = [_MSG("cm_1", "user", "Q1")];
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor(messages)))}
        meDisplayName="Sean"
      />,
    );
    const bubble = screen.getByTestId("chat-bubble");
    expect(bubble.getAttribute("data-role")).toBe("user");
    expect(bubble.className).toContain("justify-end");
    // The inner pill carries the primary background token.
    const pill = bubble.firstElementChild as HTMLElement;
    expect(pill.className).toContain("bg-(--color-primary)");
  });

  test("(6.3b) assistant ChatBubble is left-aligned with --color-card surface + border", () => {
    const messages = [_MSG("cm_2", "advisor", "A1")];
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor(messages)))}
        meDisplayName="Sean"
      />,
    );
    const bubble = screen.getByTestId("chat-bubble");
    expect(bubble.getAttribute("data-role")).toBe("advisor");
    expect(bubble.className).toContain("justify-start");
    // ─── /6.3b ───
    const pill = bubble.firstElementChild as HTMLElement;
    expect(pill.className).toContain("bg-(--color-muted)");
    expect(pill.className).toContain("border-(--color-border)");
  });

  test("(6.3c) idle in_progress with no in-flight renders 3 suggestion chips", () => {
    render(<AdvisorPane session={_stubSession(_inProgressState())} meDisplayName="Sean" />);
    const chips = screen.getAllByTestId("advisor-suggestion-chip");
    expect(chips).toHaveLength(3);
  });

  test("(6.3d) clicking a suggestion chip prefills the chat input textarea", async () => {
    render(<AdvisorPane session={_stubSession(_inProgressState())} meDisplayName="Sean" />);
    const chip = screen.getAllByTestId("advisor-suggestion-chip")[0]!;
    const expectedText = chip.textContent ?? "";
    fireEvent.click(chip);

    // useEffect inside ChatInput is microtask-deferred; wait one tick.
    await Promise.resolve();
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    expect(ta.value).toBe(expectedText);
  });

  test("(6.3) suggestions disappear when an in-flight advice is streaming", () => {
    const inFlight: InFlightAdvice = {
      requestId: "r1",
      userContent: "X",
      advisorTokens: "abc",
      status: "streaming",
      source: "chatbox",
    };
    render(
      <AdvisorPane
        session={_stubSession(_inProgressState(_advisor([], inFlight)))}
        meDisplayName="Sean"
      />,
    );
    expect(screen.queryByTestId("advisor-suggestions")).toBeNull();
  });
});
