/**
 * AdvisorPane — slice-8 right-column TacticalAdvisor surface tests.
 *
 * Per spec tactical-advisor + meeting-detail-layout ADDED requirements:
 * - hides Get Advice button when phase != in_progress (advisor needs live ctx)
 * - keeps prior advice cards visible (history) ordered oldest → newest
 * - streaming card body grows token-by-token via MarkdownPreview
 * - failed card surfaces a Retry button bound to session.requestAdvice()
 * - disables Get Advice while a request is streaming (prevents pile-up)
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { AdvisorPane } from "./advisor-pane";
import type {
  AdviceRequest,
  SessionState,
  UseMeetingSessionResult,
} from "../hooks/use-meeting-session";

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
    ...overrides,
  };
}

function _idleState(advisorRequests: AdviceRequest[] = []): SessionState {
  return { phase: "idle", advisor: { requests: advisorRequests } };
}

function _inProgressState(advisorRequests: AdviceRequest[] = []): SessionState {
  return {
    phase: "in_progress",
    chunks: [],
    silenceSinceByStream: { me: null, counterparty: null },
    streamStatus: { me: "active", counterparty: "active" },
    advisor: { requests: advisorRequests },
  };
}

describe("AdvisorPane", () => {
  test("phase=idle shows empty state and HIDES the Get Advice button", () => {
    render(<AdvisorPane session={_stubSession(_idleState())} />);
    expect(screen.queryByTestId("advisor-pane-empty")).not.toBeNull();
    expect(screen.queryByTestId("get-advice-button")).toBeNull();
  });

  test("two consecutive done requests render two cards in array order (oldest first)", () => {
    const reqs: AdviceRequest[] = [
      {
        requestId: "req_1",
        startedAt: "2026-05-10T10:00:00Z",
        status: "done",
        tokens: "first advice",
      },
      {
        requestId: "req_2",
        startedAt: "2026-05-10T10:05:00Z",
        status: "done",
        tokens: "second advice",
      },
    ];
    render(<AdvisorPane session={_stubSession(_inProgressState(reqs))} />);
    const cards = screen.getAllByTestId("advice-card");
    expect(cards).toHaveLength(2);
    // First card should be the oldest (req_1).
    expect(cards[0]!.textContent).toContain("first advice");
    expect(cards[1]!.textContent).toContain("second advice");
  });

  test("streaming request body shows the accumulated tokens via MarkdownPreview", () => {
    const reqs: AdviceRequest[] = [
      {
        requestId: "req_1",
        startedAt: "2026-05-10T10:00:00Z",
        status: "streaming",
        tokens: "abc",
      },
    ];
    render(<AdvisorPane session={_stubSession(_inProgressState(reqs))} />);
    // MarkdownPreview wraps the body in [data-testid="markdown-preview"].
    const preview = screen.getByTestId("markdown-preview");
    expect(preview.textContent).toContain("abc");
    // Streaming card surfaces the "thinking" indicator next to the heading.
    expect(screen.queryByTestId("advice-thinking")).not.toBeNull();
  });

  test("failed request renders Retry button; clicking it calls session.requestAdvice", () => {
    const requestAdvice = mock(() => {});
    const reqs: AdviceRequest[] = [
      {
        requestId: "req_x",
        startedAt: "2026-05-10T10:00:00Z",
        status: "failed",
        tokens: "",
        error: { code: "advisor.timeout", message: "Vertex timed out" },
      },
    ];
    render(<AdvisorPane session={_stubSession(_inProgressState(reqs), { requestAdvice })} />);
    const retry = screen.getByTestId("advice-retry-button");
    fireEvent.click(retry);
    expect(requestAdvice).toHaveBeenCalledTimes(1);
    // The localized timeout error text (zh-TW default) should appear.
    expect(screen.getByTestId("advice-card").textContent).toContain("逾時");
  });

  test("Get Advice button is disabled while last request is streaming", () => {
    const reqs: AdviceRequest[] = [
      {
        requestId: "req_1",
        startedAt: "2026-05-10T10:00:00Z",
        status: "streaming",
        tokens: "...",
      },
    ];
    render(<AdvisorPane session={_stubSession(_inProgressState(reqs))} />);
    const button = screen.getByTestId("get-advice-button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });
});
