/**
 * Tests for pickMeetingRecording / miniPlayerStore — slice-16 task 10.6.
 *
 * `pickMeetingRecording`:
 *   (a) single recording → that one
 *   (b) dual recordings → me stream
 *   (c) empty list → null
 *
 * `miniPlayerStore.seekToChunk`:
 *   (d) sets seek_target_seconds to (chunk.started_at - recording.started_at)
 *   (e) sets is_playing true
 *   (f) ackSeek clears the target so the player ref can re-trigger
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import {
  miniPlayerStore,
  pickMeetingRecording,
  type Recording,
  type TranscriptChunkLike,
} from "./use-mini-player";

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

const _chunk1: TranscriptChunkLike = {
  id: "c1",
  speaker: "me",
  started_at: "2026-05-15T10:00:05Z", // 5 seconds after recording start
  ended_at: "2026-05-15T10:00:10Z",
};
const _chunk2: TranscriptChunkLike = {
  id: "c2",
  speaker: "counterparty",
  started_at: "2026-05-15T10:00:20Z", // 20 seconds after recording start
  ended_at: "2026-05-15T10:00:25Z",
};

beforeEach(() => {
  miniPlayerStore._reset();
});

afterEach(() => {
  miniPlayerStore._reset();
});

describe("pickMeetingRecording", () => {
  test("(a) single recording → returns it", () => {
    expect(pickMeetingRecording([_recordingMe])?.id).toBe("r_m");
  });

  test("(b) dual recordings → me stream", () => {
    expect(pickMeetingRecording([_recordingC, _recordingMe])?.id).toBe("r_m");
  });

  test("(c) empty list → null", () => {
    expect(pickMeetingRecording([])).toBeNull();
  });

  test("(d) dual but no me stream → first recording (defensive)", () => {
    const onlyOther: Recording = { ..._recordingC, id: "r_other", stream: "other" };
    expect(pickMeetingRecording([_recordingC, onlyOther])?.id).toBe("r_c");
  });
});

describe("miniPlayerStore.seekToChunk", () => {
  test("(d) sets seek_target_seconds to chunk offset within recording", () => {
    miniPlayerStore.setContext({
      meeting_id: "m1",
      chunks: [_chunk1, _chunk2],
      recordings: [_recordingMe],
    });
    miniPlayerStore.seekToChunk("c2");
    const state = miniPlayerStore.getState();
    expect(state.seek_target_seconds).toBe(20);
    expect(state.is_playing).toBe(true);
  });

  test("(e) ackSeek clears seek_target_seconds", () => {
    miniPlayerStore.setContext({
      meeting_id: "m1",
      chunks: [_chunk1],
      recordings: [_recordingMe],
    });
    miniPlayerStore.seekToChunk("c1");
    expect(miniPlayerStore.getState().seek_target_seconds).toBe(5);
    miniPlayerStore.ackSeek();
    expect(miniPlayerStore.getState().seek_target_seconds).toBeNull();
  });

  test("(f) seek_token increments on every seekToChunk call", () => {
    miniPlayerStore.setContext({
      meeting_id: "m1",
      chunks: [_chunk1, _chunk2],
      recordings: [_recordingMe],
    });
    const before = miniPlayerStore.getState().seek_token;
    miniPlayerStore.seekToChunk("c1");
    miniPlayerStore.seekToChunk("c1"); // same chunk, second click
    expect(miniPlayerStore.getState().seek_token).toBe(before + 2);
  });
});

describe("miniPlayerStore.next / prev", () => {
  test("next steps to the chunk after the current seek target", () => {
    miniPlayerStore.setContext({
      meeting_id: "m1",
      chunks: [_chunk1, _chunk2],
      recordings: [_recordingMe],
    });
    miniPlayerStore.seekToChunk("c1"); // seek_target = 5
    miniPlayerStore.next();
    expect(miniPlayerStore.getState().seek_target_seconds).toBe(20);
  });

  test("prev steps back to the previous chunk", () => {
    miniPlayerStore.setContext({
      meeting_id: "m1",
      chunks: [_chunk1, _chunk2],
      recordings: [_recordingMe],
    });
    miniPlayerStore.seekToChunk("c2"); // seek_target = 20
    miniPlayerStore.prev();
    expect(miniPlayerStore.getState().seek_target_seconds).toBe(5);
  });
});

describe("miniPlayerStore.setRate", () => {
  test("setRate persists to localStorage", () => {
    miniPlayerStore.setRate(1.5);
    expect(window.localStorage.getItem("miniPlayerRate")).toBe("1.5");
    expect(miniPlayerStore.getState().playback_rate).toBe(1.5);
  });
});
