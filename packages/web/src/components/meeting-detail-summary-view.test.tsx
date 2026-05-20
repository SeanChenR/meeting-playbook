/**
 * MeetingDetailSummaryView — covers refactor tasks 7.1, 11.1 (3 example chips),
 * 9.5.1 (no emoji).
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { i18n } from "../lib/i18n";
import { ThemeProvider } from "../lib/theme-provider";
import { MeetingDetailSummaryView } from "./meeting-detail-summary-view";

mock.module("../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: { user: { name: "Sean", email: "sean@example.com" } },
      isPending: false,
    }),
  },
}));

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
const originalFetch = globalThis.fetch;

afterEach(cleanup);

beforeEach(() => {
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
});

function _mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider initialTheme="light">
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={qc}>
          <MeetingDetailSummaryView
            meetingId="m_1"
            meeting={{
              title: "Test",
              created_at: "2026-05-20T00:00:00Z",
              status: "completed",
            }}
          />
        </QueryClientProvider>
      </I18nextProvider>
    </ThemeProvider>,
  );
}

describe("MeetingDetailSummaryView", () => {
  test("(7.1a) renders meeting-summary-view with two equal columns", () => {
    _mount();
    const view = screen.getByTestId("meeting-summary-view");
    expect(view).toBeDefined();
    expect(view.style.gridTemplateColumns).toBe("1fr 1fr");
  });

  test("(7.1b) right column has data-testid meeting-summary-chat-slot with MessageSquare icon + 摘要對話 title + 即將推出 placeholder", () => {
    _mount();
    const slot = screen.getByTestId("meeting-summary-chat-slot");
    expect(slot).toBeDefined();
    expect(slot.textContent ?? "").toContain("摘要對話");
    expect(slot.textContent ?? "").toContain("即將推出");
    expect(slot.querySelector("svg")).not.toBeNull();
  });

  test("(11.1a) three example chips render with exact hardcoded text + cursor-default + no onClick", () => {
    _mount();
    const chipsContainer = screen.getByTestId("meeting-summary-chat-example-chips");
    const chips = chipsContainer.querySelectorAll("span");
    expect(chips.length).toBe(3);
    const texts = Array.from(chips).map((c) => c.textContent);
    expect(texts).toEqual([
      "「Joyce 那項做完了嗎？」",
      "「對方資安要求摘要」",
      "「下次該準備什麼？」",
    ]);
    // Each chip is <span> with cursor-default; <button> would have role=button
    chips.forEach((c) => {
      expect(c.tagName).toBe("SPAN");
      expect(c.className).toContain("cursor-default");
    });
  });

  test("(7.1c) no /chat or /summary-qa fetch is fired by the chat slot", () => {
    const calls: string[] = [];
    fetchHandler = async (url) => {
      calls.push(url);
      return new Response("[]", { status: 200 });
    };
    _mount();
    // SummaryPane on the left WILL fetch its summary endpoint; we only assert
    // the chat slot does NOT fetch /chat or /summary-qa.
    expect(calls.some((u) => u.includes("/chat") || u.includes("/summary-qa"))).toBe(false);
  });

  test("(9.5.1) no emoji glyphs in rendered view", () => {
    _mount();
    const view = screen.getByTestId("meeting-summary-view");
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(view.textContent ?? "")).toBe(false);
  });
});

// Restore fetch after tests
afterEach(() => {
  globalThis.fetch = originalFetch;
});
