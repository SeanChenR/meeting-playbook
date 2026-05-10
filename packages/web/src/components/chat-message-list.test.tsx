/**
 * ChatMessageList — slice-9 chat history rendering tests.
 *
 * Per spec tactical-advisor MODIFIED requirement scenario "History list
 * renders persisted chat_message rows from React Query cache" — bubbles
 * carry data-role and render in source order.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { ChatMessageList } from "./chat-message-list";
import type { ChatMessage } from "../lib/chat-api";

afterEach(cleanup);

const _MSGS: ChatMessage[] = [
  {
    id: "cm_1",
    meeting_id: "m_x",
    role: "user",
    content: "問題A",
    created_at: "2026-05-10T10:00:00Z",
  },
  {
    id: "cm_2",
    meeting_id: "m_x",
    role: "advisor",
    content: "回答A",
    created_at: "2026-05-10T10:00:01Z",
  },
  {
    id: "cm_3",
    meeting_id: "m_x",
    role: "user",
    content: "問題B",
    created_at: "2026-05-10T10:01:00Z",
  },
  {
    id: "cm_4",
    meeting_id: "m_x",
    role: "advisor",
    content: "回答B",
    created_at: "2026-05-10T10:01:01Z",
  },
];

describe("ChatMessageList", () => {
  test("renders one bubble per message with the right data-role attribute", () => {
    render(<ChatMessageList messages={_MSGS} meDisplayName="Sean" />);
    const bubbles = screen.getAllByTestId("chat-bubble");
    expect(bubbles).toHaveLength(4);
    expect(bubbles[0]!.getAttribute("data-role")).toBe("user");
    expect(bubbles[1]!.getAttribute("data-role")).toBe("advisor");
    expect(bubbles[2]!.getAttribute("data-role")).toBe("user");
    expect(bubbles[3]!.getAttribute("data-role")).toBe("advisor");
  });

  test("bubbles render in source order matching the messages array", () => {
    render(<ChatMessageList messages={_MSGS} meDisplayName="Sean" />);
    const bubbles = screen.getAllByTestId("chat-bubble");
    expect(bubbles[0]!.textContent).toContain("問題A");
    expect(bubbles[1]!.textContent).toContain("回答A");
    expect(bubbles[2]!.textContent).toContain("問題B");
    expect(bubbles[3]!.textContent).toContain("回答B");
  });

  test("user bubbles show the meeting's me display name; advisor bubbles show 'Advisor'", () => {
    render(<ChatMessageList messages={_MSGS} meDisplayName="Sean" />);
    const bubbles = screen.getAllByTestId("chat-bubble");
    // user bubble headers contain "Sean"
    expect(bubbles[0]!.textContent).toContain("Sean");
    // advisor bubble headers contain literal "Advisor"
    expect(bubbles[1]!.textContent).toContain("Advisor");
  });

  test("empty messages array renders nothing (no list element)", () => {
    render(<ChatMessageList messages={[]} meDisplayName="Sean" />);
    expect(screen.queryByTestId("chat-message-list")).toBeNull();
    expect(screen.queryAllByTestId("chat-bubble")).toHaveLength(0);
  });
});
