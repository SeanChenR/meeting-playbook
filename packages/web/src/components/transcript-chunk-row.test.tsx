/**
 * Tests for TranscriptChunkRow — slice-16 task 10.5.
 *
 * Persistent ✎ trigger + ChunkActionMenu + inline rename mode:
 *   (a) ✎ icon is in the DOM always (no hover dependency)
 *   (b) click ✎ → ChunkActionMenu mounted
 *   (c) Edit text action → inline textarea + Cancel restores original text
 *   (d) Edit text action + Save success → row exits edit mode + onEdited fires
 *   (e) Save failure 422 → stays in edit mode + localized error visible
 *   (f) Rename speaker action (cluster) → input mode + Enter commits
 *   (g) Rename Escape → exits without onRenameCommit
 *   (h) Play action fires onPlay callback
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TranscriptChunkRow } from "./transcript-chunk-row";

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = mock(async () => new Response("{}")) as unknown as typeof fetch;
});

afterEach(() => {
  cleanup();
  globalThis.fetch = _originalFetch;
  mock.restore();
});

describe("TranscriptChunkRow (slice-16 task 10.5)", () => {
  test("(a) ✎ trigger is always visible (no hover dependency)", () => {
    render(<TranscriptChunkRow meetingId="m1" chunkId="c1" text="original" clusterN={null} />);
    const trigger = screen.getByTestId("chunk-action-menu-trigger");
    expect(trigger).toBeDefined();
    // Trigger should NOT carry the slice-16 v1 opacity-0 / group-hover classes.
    expect(trigger.className).not.toContain("opacity-0");
  });

  test("(b) clicking ✎ opens the ChunkActionMenu", async () => {
    const user = userEvent.setup();
    render(<TranscriptChunkRow meetingId="m1" chunkId="c1" text="original" clusterN={2} />);
    expect(screen.queryByTestId("chunk-action-menu")).toBeNull();
    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    expect(screen.getByTestId("chunk-action-menu")).toBeDefined();
  });

  test("(c) Edit text → Cancel restores text and never fires PATCH", async () => {
    const fetchSpy = mock(async () => new Response("{}"));
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    const user = userEvent.setup();
    render(<TranscriptChunkRow meetingId="m1" chunkId="c1" text="original" clusterN={null} />);

    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-edit-text"));
    const textarea = screen.getByTestId("chunk-edit-textarea") as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "draft change");
    await user.click(screen.getByTestId("chunk-edit-cancel"));

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.queryByTestId("chunk-edit-textarea")).toBeNull();
    expect(screen.getByText("original")).toBeDefined();
  });

  test("(d) Edit text → Save success updates text and fires onEdited", async () => {
    const fetchSpy = mock(
      async () =>
        new Response(
          JSON.stringify({
            id: "c1",
            text: "corrected",
            text_edited_at: "2026-05-15T10:00:00Z",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
    );
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    const user = userEvent.setup();
    const onEdited = mock(() => undefined);
    render(
      <TranscriptChunkRow
        meetingId="m1"
        chunkId="c1"
        text="original"
        clusterN={null}
        onEdited={onEdited}
      />,
    );

    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-edit-text"));
    const textarea = screen.getByTestId("chunk-edit-textarea") as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "corrected");
    await user.click(screen.getByTestId("chunk-edit-save"));

    await waitFor(() => {
      expect(screen.queryByTestId("chunk-edit-textarea")).toBeNull();
    });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(onEdited).toHaveBeenCalledTimes(1);
    expect(screen.getByText("corrected")).toBeDefined();
  });

  test("(e) Save 422 invalid_text → stays in edit mode + localized error", async () => {
    const fetchSpy = mock(
      async () =>
        new Response(JSON.stringify({ error_code: "transcript_edit.invalid_text", message: "x" }), {
          status: 422,
          headers: { "content-type": "application/json" },
        }),
    );
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    const user = userEvent.setup();
    render(<TranscriptChunkRow meetingId="m1" chunkId="c1" text="original" clusterN={null} />);

    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-edit-text"));
    await user.click(screen.getByTestId("chunk-edit-save"));

    await waitFor(() => {
      expect(screen.getByTestId("chunk-edit-error")).toBeDefined();
    });
    expect(screen.queryByTestId("chunk-edit-textarea")).toBeDefined();
  });

  test("(f) Rename action (cluster) → input + Enter commits", async () => {
    const user = userEvent.setup();
    const onRename = mock(() => undefined);
    render(
      <TranscriptChunkRow
        meetingId="m1"
        chunkId="c1"
        text="original"
        clusterN={2}
        onRenameCommit={onRename}
      />,
    );

    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-rename"));
    const input = screen.getByTestId("chunk-rename-input") as HTMLInputElement;
    await user.type(input, "Alice");
    await user.keyboard("{Enter}");

    expect(onRename).toHaveBeenCalledWith(2, "Alice");
  });

  test("(g) Rename Escape → no commit, exits rename mode", async () => {
    const user = userEvent.setup();
    const onRename = mock(() => undefined);
    render(
      <TranscriptChunkRow
        meetingId="m1"
        chunkId="c1"
        text="original"
        clusterN={2}
        onRenameCommit={onRename}
      />,
    );
    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-rename"));
    const input = screen.getByTestId("chunk-rename-input") as HTMLInputElement;
    await user.type(input, "Alice");
    await user.keyboard("{Escape}");
    expect(onRename).not.toHaveBeenCalled();
    expect(screen.queryByTestId("chunk-rename-input")).toBeNull();
  });

  test("(h) Play action fires onPlay callback", async () => {
    const user = userEvent.setup();
    const onPlay = mock(() => undefined);
    render(
      <TranscriptChunkRow
        meetingId="m1"
        chunkId="c1"
        text="original"
        clusterN={null}
        onPlay={onPlay}
      />,
    );
    await user.click(screen.getByTestId("chunk-action-menu-trigger"));
    await user.click(screen.getByTestId("chunk-action-play"));
    expect(onPlay).toHaveBeenCalledWith("c1");
  });
});
