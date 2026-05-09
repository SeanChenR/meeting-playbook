/**
 * TranscriptPane — chronological transcript chunks attributed to me_display_name.
 *
 * Per spec meeting-session ADDED requirement scenarios:
 * - "Empty chunks renders an empty state"
 * - "Chunks attributed to me_display_name"
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { TranscriptPane } from "./transcript-pane";
import type { TranscriptChunkMessage } from "../lib/session-ws";

afterEach(cleanup);

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
    render(<TranscriptPane chunks={[]} meDisplayName="Sean" />);
    expect(screen.getByTestId("transcript-empty")).toBeDefined();
  });

  test("renders three me-chunks in arrival order with meDisplayName attribution", () => {
    const chunks = [
      _chunk("first", "me", "2026-05-09T10:00:00Z"),
      _chunk("second", "me", "2026-05-09T10:00:10Z"),
      _chunk("third", "me", "2026-05-09T10:00:20Z"),
    ];
    render(<TranscriptPane chunks={chunks} meDisplayName="Sean Chen" />);

    const items = screen.getAllByTestId("transcript-chunk");
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent).toContain("first");
    expect(items[1]?.textContent).toContain("second");
    expect(items[2]?.textContent).toContain("third");
    // Every me-chunk shows the meeting's me_display_name as speaker.
    for (const item of items) {
      expect(item.textContent).toContain("Sean Chen");
    }
  });

  test("counterparty-speaker chunk gets a different visual style than me", () => {
    const chunks = [_chunk("from-other-side", "counterparty")];
    render(<TranscriptPane chunks={chunks} meDisplayName="Sean" />);
    const item = screen.getByTestId("transcript-chunk");
    expect(item.dataset.speaker).toBe("counterparty");
  });
});
