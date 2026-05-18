/**
 * Unit tests for `pickPlaybackSources` — slice-25 task 3.2.
 *
 * Covers the source-toggle resolution logic per spec audio-playback
 * MODIFIED requirement "MeetingAudioMiniPlayer is a sticky bottom control
 * bar with whole-recording playback" (the `pickPlaybackSources` portion).
 */

import { describe, expect, test } from "bun:test";

import { type Recording, pickPlaybackSources } from "./use-mini-player";

function _rec(over: Partial<Recording> = {}): Recording {
  return {
    id: "r_default",
    meeting_id: "m_x",
    stream: "me",
    file_path: "/tmp/me.wav",
    bytes: 1024,
    created_at: "2026-05-18T00:00:00Z",
    started_at: "2026-05-18T00:00:00Z",
    deleted_at: null,
    source: "live",
    ...over,
  };
}

describe("pickPlaybackSources", () => {
  test("dual-channel returns mixed default with three source URLs", () => {
    const result = pickPlaybackSources("m_dual", [
      _rec({ id: "r_me", stream: "me" }),
      _rec({ id: "r_cp", stream: "counterparty" }),
    ]);
    expect(result.kind).toBe("dual");
    expect(result.defaultSource).toBe("mixed");
    expect(result.sources.mixed).toBe("/api/meetings/m_dual/recordings/mixed/audio");
    expect(result.sources.me).toBe("/api/meetings/m_dual/recordings/r_me/audio");
    expect(result.sources.counterparty).toBe("/api/meetings/m_dual/recordings/r_cp/audio");
  });

  test("single-channel (me only) returns me default, no mixed", () => {
    const result = pickPlaybackSources("m_solo", [_rec({ id: "r_solo", stream: "me" })]);
    expect(result.kind).toBe("single");
    expect(result.defaultSource).toBe("me");
    expect(result.sources.me).toBe("/api/meetings/m_solo/recordings/r_solo/audio");
    expect(result.sources.mixed).toBeUndefined();
    expect(result.sources.counterparty).toBeUndefined();
  });

  test("single-channel (counterparty only) still routes through .sources.me URL", () => {
    // Edge: an offline-ingest path could in theory produce a single counterparty
    // recording. The toggle UI doesn't render anyway; the single URL goes in
    // `.sources.me` so the mini-player can use a uniform default.
    const result = pickPlaybackSources("m_cp_only", [_rec({ id: "r_cp", stream: "counterparty" })]);
    expect(result.kind).toBe("single");
    expect(result.defaultSource).toBe("me");
    expect(result.sources.me).toBe("/api/meetings/m_cp_only/recordings/r_cp/audio");
  });

  test("no recordings returns kind=none with empty sources", () => {
    const result = pickPlaybackSources("m_empty", []);
    expect(result.kind).toBe("none");
    expect(result.sources).toEqual({});
    expect(result.defaultSource).toBe("me");
  });
});
