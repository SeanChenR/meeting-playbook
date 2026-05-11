/**
 * TranscriptPane — chronological transcript chunks attributed to me_display_name.
 *
 * Per spec meeting-session ADDED requirement scenarios:
 * - "Empty chunks renders an empty state"
 * - "Chunks attributed to me_display_name"
 */

import { afterEach, describe, expect, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { TranscriptPane } from "./transcript-pane";
import type { TranscriptChunkMessage } from "../lib/session-ws";

afterEach(cleanup);

// Slice-11: TranscriptPane now always calls useQuery (driven by the
// rerun-status polling). Tests need a QueryClient even when they don't
// exercise the polling path.
function _Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function _render(ui: ReactNode) {
  return render(<_Wrapper>{ui}</_Wrapper>);
}

const _chunk = (
  text: string,
  speaker: TranscriptChunkMessage["speaker"] = "me",
  startedAt = "2026-05-09T10:00:00Z",
): TranscriptChunkMessage => ({
  type: "transcript_chunk",
  meeting_id: "m_t",
  speaker,
  text,
  started_at: startedAt,
  ended_at: "2026-05-09T10:00:10Z",
  asr_provider_used: "whisper",
  confidence: 0.9,
});

describe("TranscriptPane", () => {
  test("empty chunks renders a placeholder, not an empty list", () => {
    _render(<TranscriptPane chunks={[]} meDisplayName="Sean" counterpartyDisplayName="林經理" />);
    expect(screen.getByTestId("transcript-empty")).toBeDefined();
  });

  test("renders three me-chunks in arrival order with meDisplayName attribution", () => {
    const chunks = [
      _chunk("first", "me", "2026-05-09T10:00:00Z"),
      _chunk("second", "me", "2026-05-09T10:00:10Z"),
      _chunk("third", "me", "2026-05-09T10:00:20Z"),
    ];
    _render(
      <TranscriptPane chunks={chunks} meDisplayName="Sean Chen" counterpartyDisplayName="林經理" />,
    );

    const items = screen.getAllByTestId("transcript-chunk");
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent).toContain("first");
    expect(items[1]?.textContent).toContain("second");
    expect(items[2]?.textContent).toContain("third");
    for (const item of items) {
      expect(item.textContent).toContain("Sean Chen");
    }
  });

  // ─── Slice 7 ─────────────────────────────────────────────────────

  test("counterparty chunk applies primary accent border", () => {
    const chunks = [_chunk("from-other-side", "counterparty")];
    _render(
      <TranscriptPane chunks={chunks} meDisplayName="Sean" counterpartyDisplayName="林經理" />,
    );
    const item = screen.getByTestId("transcript-chunk");
    expect(item.dataset.speaker).toBe("counterparty");
    // border-l-4 token sits on the chunk wrapper; counterparty gets primary.
    expect(item.className).toContain("border-l-(--color-primary)");
    expect(item.className).not.toContain("border-l-(--color-muted-foreground)");
  });

  test("me chunk applies muted-foreground accent border", () => {
    const chunks = [_chunk("from-me", "me")];
    _render(
      <TranscriptPane chunks={chunks} meDisplayName="Sean" counterpartyDisplayName="林經理" />,
    );
    const item = screen.getByTestId("transcript-chunk");
    expect(item.dataset.speaker).toBe("me");
    expect(item.className).toContain("border-l-(--color-muted-foreground)");
    expect(item.className).not.toContain("border-l-(--color-primary)");
  });

  test("uses counterpartyDisplayName for counterparty chunks", () => {
    const chunks = [_chunk("hi from me", "me"), _chunk("hi from them", "counterparty")];
    _render(
      <TranscriptPane chunks={chunks} meDisplayName="Sean" counterpartyDisplayName="林經理" />,
    );
    const items = screen.getAllByTestId("transcript-chunk");
    expect(items[0]?.textContent).toContain("Sean");
    expect(items[0]?.textContent).not.toContain("林經理");
    expect(items[1]?.textContent).toContain("林經理");
    expect(items[1]?.textContent).not.toContain("Sean");
  });
});
