/**
 * Mini-player store + chunk seek resolver — slice-16 task 10.6.
 *
 * The store is a module-scoped singleton wired through
 * `useSyncExternalStore` so the `<MeetingAudioMiniPlayer>` and any chunk
 * action menu can share playback state without prop drilling.
 *
 * Slice-16 task 10.6 redesigned the contract: the mini-player loads
 * the entire recording WAV file ONCE on mount (the meeting's `me`-stream
 * recording for dual-channel, the only recording for single-channel).
 * Chunk-level "play this chunk" sets `seek_target_seconds` instead of
 * switching the `<audio>` element's `src` — the player ref reacts to
 * the target and adjusts `currentTime`.
 *
 * Playback rate persists to `localStorage.miniPlayerRate`.
 */

import { useSyncExternalStore } from "react";

import { type Meeting, mixedAudioUrl, recordingAudioUrl } from "../lib/meetings-api";

export interface Recording {
  id: string;
  meeting_id: string;
  stream: string;
  file_path: string;
  bytes: number;
  created_at: string;
  started_at: string;
  deleted_at: string | null;
  source: string;
}

export interface TranscriptChunkLike {
  id: string;
  speaker: string;
  started_at: string;
  ended_at: string;
}

export const PLAYBACK_RATES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0] as const;
export type PlaybackRate = (typeof PLAYBACK_RATES)[number];

const RATE_STORAGE_KEY = "miniPlayerRate";

interface MiniPlayerState {
  /**
   * Seconds offset (relative to recording.started_at) the player should
   * jump to. The player ref consumes this and resets it to `null` so
   * subsequent `seekToChunk(sameId)` calls still fire.
   */
  seek_target_seconds: number | null;
  /** Monotonic counter so consumers can react to repeated seeks to the same offset. */
  seek_token: number;
  playback_rate: PlaybackRate;
  is_playing: boolean;
  chunks_sorted: TranscriptChunkLike[];
  recordings: Recording[];
  meeting_id: string | null;
}

function _readPersistedRate(): PlaybackRate {
  if (typeof window === "undefined") return 1.0;
  const raw = window.localStorage.getItem(RATE_STORAGE_KEY);
  if (!raw) return 1.0;
  const parsed = Number.parseFloat(raw);
  return (PLAYBACK_RATES as readonly number[]).includes(parsed) ? (parsed as PlaybackRate) : 1.0;
}

let _state: MiniPlayerState = {
  seek_target_seconds: null,
  seek_token: 0,
  playback_rate: _readPersistedRate(),
  is_playing: false,
  chunks_sorted: [],
  recordings: [],
  meeting_id: null,
};

const _listeners = new Set<() => void>();

function _emit() {
  for (const listener of _listeners) listener();
}

function _setState(
  updater: Partial<MiniPlayerState> | ((prev: MiniPlayerState) => Partial<MiniPlayerState>),
): void {
  const patch = typeof updater === "function" ? updater(_state) : updater;
  _state = { ..._state, ...patch };
  _emit();
}

function _chunkSeekTarget(chunk: TranscriptChunkLike, recording: Recording): number {
  const chunkMs = new Date(chunk.started_at).getTime();
  const recMs = new Date(recording.started_at).getTime();
  if (!Number.isFinite(chunkMs) || !Number.isFinite(recMs)) return 0;
  return Math.max(0, (chunkMs - recMs) / 1000);
}

export const miniPlayerStore = {
  getState: () => _state,
  subscribe: (listener: () => void) => {
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  },
  setContext: (params: {
    meeting_id: string;
    chunks: TranscriptChunkLike[];
    recordings: Recording[];
  }) => {
    const chunks_sorted = [...params.chunks].sort((a, b) =>
      a.started_at.localeCompare(b.started_at),
    );
    _setState({
      meeting_id: params.meeting_id,
      chunks_sorted,
      recordings: params.recordings,
    });
  },
  seekToChunk: (chunkId: string) => {
    const chunk = _state.chunks_sorted.find((c) => c.id === chunkId);
    const recording = pickMeetingRecording(_state.recordings);
    if (!chunk || !recording) return;
    _setState((prev) => ({
      seek_target_seconds: _chunkSeekTarget(chunk, recording),
      seek_token: prev.seek_token + 1,
      is_playing: true,
    }));
  },
  /** Consumer (the audio ref) calls this once it has applied the seek. */
  ackSeek: () => {
    _setState({ seek_target_seconds: null });
  },
  pause: () => {
    _setState({ is_playing: false });
  },
  togglePlay: () => {
    _setState((prev) => ({ is_playing: !prev.is_playing }));
  },
  next: () => {
    const recording = pickMeetingRecording(_state.recordings);
    if (!recording || _state.chunks_sorted.length === 0) return;
    const currentSeconds = _state.seek_target_seconds;
    // Find the first chunk whose start is strictly after the current
    // seek target (falling back to 0 when seek_target is null).
    const cur = currentSeconds ?? 0;
    const nextChunk = _state.chunks_sorted.find((c) => _chunkSeekTarget(c, recording) > cur + 0.01);
    if (!nextChunk) return;
    miniPlayerStore.seekToChunk(nextChunk.id);
  },
  prev: () => {
    const recording = pickMeetingRecording(_state.recordings);
    if (!recording || _state.chunks_sorted.length === 0) return;
    const cur = _state.seek_target_seconds ?? 0;
    // Find the latest chunk whose start is strictly before the current
    // seek target.
    const prevChunk = [..._state.chunks_sorted]
      .reverse()
      .find((c) => _chunkSeekTarget(c, recording) < cur - 0.01);
    if (!prevChunk) return;
    miniPlayerStore.seekToChunk(prevChunk.id);
  },
  setRate: (rate: PlaybackRate) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(RATE_STORAGE_KEY, String(rate));
    }
    _setState({ playback_rate: rate });
  },
  /** Test helper: reset the store between tests. Not for production code paths. */
  _reset: () => {
    _state = {
      seek_target_seconds: null,
      seek_token: 0,
      playback_rate: _readPersistedRate(),
      is_playing: false,
      chunks_sorted: [],
      recordings: [],
      meeting_id: null,
    };
    _emit();
  },
};

export function useMiniPlayerStore(): MiniPlayerState {
  return useSyncExternalStore(
    miniPlayerStore.subscribe,
    miniPlayerStore.getState,
    miniPlayerStore.getState,
  );
}

/**
 * Pick the single recording the mini-player should stream for this meeting.
 *
 * - Dual-channel meeting (≥ 2 recordings): the recording with stream `"me"`
 *   if present, otherwise the first recording.
 * - Single-channel meeting (one recording): that recording.
 * - No recordings: `null` (mini-player renders in idle state).
 *
 * Slice-16 task 10.6: replaced the per-chunk `useChunkAudioSource` resolver
 * — the mini-player no longer switches src by chunk, it streams the whole
 * `me` WAV and seeks within it.
 */
export function pickMeetingRecording(recordings: Recording[]): Recording | null {
  if (recordings.length === 0) return null;
  if (recordings.length === 1) return recordings[0] ?? null;
  return recordings.find((r) => r.stream === "me") ?? recordings[0] ?? null;
}

/** Convenience: surfaces the meeting object's id so callers can build URLs. */
export type MeetingWithId = Pick<Meeting, "id">;

// ─── slice-25 task 3.2 — source toggle resolution ───────────────────────

/** Toggle source key persisted in `localStorage.miniPlayerSource`. */
export type SourceKey = "mixed" | "me" | "counterparty";

export interface PlaybackSources {
  /** `dual` = both me + counterparty streams present (mixed available). */
  kind: "dual" | "single" | "none";
  /** Map from source key to its audio URL (only entries the meeting has). */
  sources: {
    mixed?: string;
    me?: string;
    counterparty?: string;
  };
  /** Default source the mini-player mounts on first render. */
  defaultSource: SourceKey;
}

/**
 * Resolve the URL set the source-toggle UI should expose per design D5 + D11.
 *
 * - Both me + counterparty rows → `kind: "dual"`, defaultSource `"mixed"`,
 *   sources includes mixed/me/counterparty URLs (the mixed URL hits the
 *   slice-25 mixed endpoint, me/counterparty hit the per-recording endpoint).
 * - Exactly one row → `kind: "single"`, defaultSource `"me"`, only the
 *   single recording's URL is exposed (no toggle UI rendered).
 * - Zero rows → `kind: "none"`, empty `sources`.
 */
export function pickPlaybackSources(meetingId: string, recordings: Recording[]): PlaybackSources {
  if (recordings.length === 0) {
    return { kind: "none", sources: {}, defaultSource: "me" };
  }
  const meRow = recordings.find((r) => r.stream === "me");
  const cpRow = recordings.find((r) => r.stream === "counterparty");
  if (meRow && cpRow) {
    return {
      kind: "dual",
      sources: {
        mixed: mixedAudioUrl(meetingId),
        me: recordingAudioUrl(meetingId, meRow.id),
        counterparty: recordingAudioUrl(meetingId, cpRow.id),
      },
      defaultSource: "mixed",
    };
  }
  const onlyRow = meRow ?? cpRow ?? recordings[0];
  if (!onlyRow) {
    return { kind: "none", sources: {}, defaultSource: "me" };
  }
  return {
    kind: "single",
    sources: { me: recordingAudioUrl(meetingId, onlyRow.id) },
    defaultSource: "me",
  };
}
