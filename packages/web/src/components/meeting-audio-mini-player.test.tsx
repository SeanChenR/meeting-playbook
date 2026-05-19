/**
 * Tests for MeetingAudioMiniPlayer — slice-16 task 10.7 (rewrite for
 * whole-recording playback). Verifies:
 *
 *   (a) audio src is set ONCE on mount to the me-stream recording
 *   (b) seekToChunk does NOT change src (only currentTime / store target)
 *   (c) speed select updates playbackRate without changing src
 *   (d) Next button steps to next chunk (store delegates to seekToChunk)
 *   (e) idle (no recording) → all transport controls disabled
 *   (f) seek bar input is wired (range element present, accessible label)
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import "../test-setup";
import "../lib/i18n";

import { MeetingAudioMiniPlayer } from "./meeting-audio-mini-player";
import {
  miniPlayerStore,
  type Recording,
  type TranscriptChunkLike,
} from "../hooks/use-mini-player";

const RATE_KEY = "miniPlayerRate";

const _recordingMe: Recording = {
  id: "r_m",
  meeting_id: "m1",
  stream: "me",
  file_path: "/tmp/me.wav",
  bytes: 1024,
  created_at: "2026-05-15T10:00:00Z",
  started_at: "2026-05-15T10:00:00Z",
  deleted_at: null,
  source: "live",
};
const _recordingC: Recording = { ..._recordingMe, id: "r_c", stream: "counterparty" };

const _chunks: TranscriptChunkLike[] = [
  {
    id: "c1",
    speaker: "me",
    started_at: "2026-05-15T10:00:05Z",
    ended_at: "2026-05-15T10:00:10Z",
  },
  {
    id: "c2",
    speaker: "counterparty",
    started_at: "2026-05-15T10:00:20Z",
    ended_at: "2026-05-15T10:00:25Z",
  },
];

beforeEach(() => {
  window.localStorage.clear();
  miniPlayerStore._reset();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  miniPlayerStore._reset();
});

describe("MeetingAudioMiniPlayer", () => {
  test("(a) dual-channel: audio src defaults to the mixed endpoint on mount", () => {
    // Per slice-25 design D5 + spec MODIFIED, dual-channel mounts mixed by default.
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingC, _recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/meetings/m1/recordings/mixed/audio");
  });

  test("(b) seekToChunk does NOT change src", () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const beforeSrc = (screen.getByTestId("mini-player-audio") as HTMLAudioElement).getAttribute(
      "src",
    );

    act(() => {
      miniPlayerStore.seekToChunk("c2");
    });

    const afterSrc = (screen.getByTestId("mini-player-audio") as HTMLAudioElement).getAttribute(
      "src",
    );
    expect(afterSrc).toBe(beforeSrc);
  });

  test("(c) speed select updates playbackRate without changing src", async () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);

    const beforeSrc = (screen.getByTestId("mini-player-audio") as HTMLAudioElement).getAttribute(
      "src",
    );

    const user = userEvent.setup();
    await user.selectOptions(screen.getByTestId("mini-player-speed"), "1.5");

    expect(miniPlayerStore.getState().playback_rate).toBe(1.5);
    const afterSrc = (screen.getByTestId("mini-player-audio") as HTMLAudioElement).getAttribute(
      "src",
    );
    expect(afterSrc).toBe(beforeSrc);
  });

  test("(d) Next button delegates to seekToChunk (seek_token increments)", async () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const tokenBefore = miniPlayerStore.getState().seek_token;
    const user = userEvent.setup();
    await user.click(screen.getByTestId("mini-player-next"));
    // seek_token incremented even though useEffect immediately ack'd
    // the target back to null.
    expect(miniPlayerStore.getState().seek_token).toBeGreaterThan(tokenBefore);
    // Audio currentTime updated to chunk c1's offset (5 seconds).
    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.currentTime).toBeCloseTo(5, 1);
  });

  test("(e) no recording → audio not mounted + transport disabled", () => {
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    expect(screen.queryByTestId("mini-player-audio")).toBeNull();
    expect((screen.getByTestId("mini-player-prev") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("mini-player-next") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("mini-player-play-toggle") as HTMLButtonElement).disabled).toBe(
      true,
    );
    // Speed dropdown stays enabled per spec scenario (d).
    expect((screen.getByTestId("mini-player-speed") as HTMLSelectElement).disabled).toBe(false);
  });

  test("(f) seek bar is mounted with accessible label", () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const seek = screen.getByTestId("mini-player-seek-bar") as HTMLInputElement;
    expect(seek.type).toBe("range");
    expect(seek.getAttribute("aria-label")?.length ?? 0).toBeGreaterThan(0);
  });

  test("(g) localStorage rate persists across remount", () => {
    window.localStorage.setItem(RATE_KEY, "0.75");
    miniPlayerStore._reset();
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    expect(miniPlayerStore.getState().playback_rate).toBe(0.75);
    const select = screen.getByTestId("mini-player-speed") as HTMLSelectElement;
    expect(select.value).toBe("0.75");
  });

  // ─── slice-25 task 4.1 — source toggle ───────────────────────────────

  test("(h) dual-channel renders three source toggle buttons with mixed active", () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe, _recordingC],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    expect(screen.queryByTestId("mini-player-source-toggle")).not.toBeNull();
    const mixedBtn = screen.getByTestId("source-mixed") as HTMLButtonElement;
    const meBtn = screen.getByTestId("source-me") as HTMLButtonElement;
    const cpBtn = screen.getByTestId("source-counterparty") as HTMLButtonElement;
    expect(mixedBtn.getAttribute("aria-pressed")).toBe("true");
    expect(meBtn.getAttribute("aria-pressed")).toBe("false");
    expect(cpBtn.getAttribute("aria-pressed")).toBe("false");
  });

  test("(i) single-channel does NOT render the source toggle", () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    expect(screen.queryByTestId("mini-player-source-toggle")).toBeNull();
    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/meetings/m1/recordings/r_m/audio");
  });

  test("(j) toggle to counterparty updates src + persists in localStorage", async () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe, _recordingC],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const user = userEvent.setup();
    await user.click(screen.getByTestId("source-counterparty"));

    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/meetings/m1/recordings/r_c/audio");
    expect(window.localStorage.getItem("miniPlayerSource")).toBe("counterparty");
    expect(
      (screen.getByTestId("source-counterparty") as HTMLButtonElement).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  test("(k) persisted source 'them' (legacy) ignored — falls back to default mixed", () => {
    // Per spec scenario "Toggle persists across page reload" — only the
    // canonical keys mixed/me/counterparty are honored.
    window.localStorage.setItem("miniPlayerSource", "them");
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe, _recordingC],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/meetings/m1/recordings/mixed/audio");
  });

  // ─── slice-25 task 4.2 — mix-failure inline error ────────────────────

  test("(m) mixed endpoint 500 renders inline alert + keeps source on mixed", async () => {
    // Per design D9: do NOT silently fall back to me-only when mixed fails.
    const _origFetch = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/recordings/mixed/audio")) {
        return new Response(
          JSON.stringify({
            error_code: "recording.mix_failed",
            message: "boom",
          }),
          { status: 500, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(null, { status: 200 });
    }) as typeof fetch;

    try {
      act(() => {
        miniPlayerStore.setContext({
          meeting_id: "m1",
          chunks: _chunks,
          recordings: [_recordingMe, _recordingC],
        });
      });
      render(<MeetingAudioMiniPlayer meetingId="m1" />);

      await waitFor(() => {
        expect(screen.queryByTestId("mini-player-mix-error")).not.toBeNull();
      });

      // Mixed button still active — no auto-fallback to me/counterparty.
      expect(
        (screen.getByTestId("source-mixed") as HTMLButtonElement).getAttribute("aria-pressed"),
      ).toBe("true");
      expect(window.localStorage.getItem("miniPlayerSource")).toBeNull();
    } finally {
      globalThis.fetch = _origFetch;
    }
  });

  // ─── ui-overhaul-animated-surfaces task 5.2 ─────────────────────
  test("mini-player chrome is a GlassDock wrapper", () => {
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe, _recordingC],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const player = screen.getByTestId("meeting-audio-mini-player");
    expect(player.className).toContain("backdrop-blur");
    expect(player.className).toContain("rounded-lg");
  });

  test("(l) persisted source 'me' is honored across mount", () => {
    window.localStorage.setItem("miniPlayerSource", "me");
    act(() => {
      miniPlayerStore.setContext({
        meeting_id: "m1",
        chunks: _chunks,
        recordings: [_recordingMe, _recordingC],
      });
    });
    render(<MeetingAudioMiniPlayer meetingId="m1" />);
    const audio = screen.getByTestId("mini-player-audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/meetings/m1/recordings/r_m/audio");
    expect(
      (screen.getByTestId("source-me") as HTMLButtonElement).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});
