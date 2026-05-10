/**
 * chat-api — chat history hydration for the AdvisorPane.
 *
 * Per spec tactical-advisor ADDED requirement scenarios "Owner GET returns
 * chronological history" / "Empty history returns 200 with empty array" /
 * "Non-owner GET returns 404 not_found" — these mirror the backend tests
 * but exercise the TS client's parsing + error envelope.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  ChatApiError,
  type ChatMessage,
  chatMessagesQueryOptions,
  listChatMessages,
} from "./chat-api";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = mock(
    async () =>
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } }),
  ) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("listChatMessages", () => {
  test("parses a 3-element array of ChatMessage objects", async () => {
    const sample: ChatMessage[] = [
      {
        id: "cm_1",
        meeting_id: "m_x",
        role: "user",
        content: "Q1",
        created_at: "2026-05-10T10:00:00Z",
      },
      {
        id: "cm_2",
        meeting_id: "m_x",
        role: "advisor",
        content: "A1",
        created_at: "2026-05-10T10:00:01Z",
      },
      {
        id: "cm_3",
        meeting_id: "m_x",
        role: "user",
        content: "Q2",
        created_at: "2026-05-10T10:01:00Z",
      },
    ];
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify(sample), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    const out = await listChatMessages("m_x");
    expect(out).toHaveLength(3);
    expect(out[0]!.role).toBe("user");
    expect(out[1]!.role).toBe("advisor");
    expect(out[2]!.content).toBe("Q2");
  });

  test("non-200 response throws ChatApiError carrying error_code + message", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(
          JSON.stringify({ error_code: "meeting.not_found", message: "Meeting not found" }),
          { status: 404, headers: { "content-type": "application/json" } },
        ),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await listChatMessages("m_missing");
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(ChatApiError);
    expect((caught as ChatApiError).status).toBe(404);
    expect((caught as ChatApiError).errorCode).toBe("meeting.not_found");
  });
});

describe("chatMessagesQueryOptions", () => {
  test("queryKey is ['chat_messages', meetingId] and enabled gate respected", () => {
    const opts = chatMessagesQueryOptions("m_x", true);
    expect(opts.queryKey).toEqual(["chat_messages", "m_x"]);
    expect(opts.enabled).toBe(true);
    const disabled = chatMessagesQueryOptions("m_x", false);
    expect(disabled.enabled).toBe(false);
  });
});
