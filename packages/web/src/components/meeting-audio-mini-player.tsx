/**
 * MeetingAudioMiniPlayer — slice-16 task 10.7 (whole-recording rewrite).
 *
 * Sticky-bottom bar mounted from the meeting detail route. Loads the
 * meeting's `me`-stream recording (or the only recording for single-channel)
 * via a single `<audio>` element whose `src` is set once on mount. Chunk
 * navigation (Prev / Next, chunk action menu "Play this chunk") seeks
 * inside the same audio element via `currentTime` — no src switching.
 *
 * Speed dropdown drives `audioRef.current.playbackRate` without affecting
 * src; the user's choice persists to `localStorage.miniPlayerRate`.
 */

import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  PLAYBACK_RATES,
  miniPlayerStore,
  pickMeetingRecording,
  useMiniPlayerStore,
  type PlaybackRate,
} from "../hooks/use-mini-player";

export interface MeetingAudioMiniPlayerProps {
  meetingId: string;
}

export function MeetingAudioMiniPlayer({ meetingId }: MeetingAudioMiniPlayerProps) {
  const { t } = useTranslation();
  const state = useMiniPlayerStore();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const recording = useMemo(() => pickMeetingRecording(state.recordings), [state.recordings]);
  const audioSrc = useMemo(() => {
    if (!recording) return null;
    return `/api/meetings/${encodeURIComponent(meetingId)}/recordings/${encodeURIComponent(
      recording.id,
    )}/audio`;
  }, [meetingId, recording]);

  // Keep <audio>.playbackRate in sync with store.
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = state.playback_rate;
    }
  }, [state.playback_rate]);

  // Apply seek_target_seconds when it changes.
  useEffect(() => {
    if (state.seek_target_seconds === null) return;
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = state.seek_target_seconds;
    miniPlayerStore.ackSeek();
  }, [state.seek_target_seconds, state.seek_token]);

  // Drive play / pause from store.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (state.is_playing) {
      el.play().catch(() => {
        miniPlayerStore.pause();
      });
    } else {
      el.pause();
    }
  }, [state.is_playing, audioSrc]);

  const idle = !audioSrc;
  const fmt = (s: number) => {
    if (!Number.isFinite(s)) return "00:00";
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <div
      data-testid="meeting-audio-mini-player"
      className="sticky bottom-0 z-30 flex flex-wrap items-center gap-2 border-t border-(--color-border) bg-(--color-card)/95 px-4 py-2 backdrop-blur"
    >
      {audioSrc && (
        <audio
          ref={audioRef}
          data-testid="mini-player-audio"
          src={audioSrc}
          preload="metadata"
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onEnded={() => miniPlayerStore.pause()}
        />
      )}

      <button
        type="button"
        data-testid="mini-player-prev"
        onClick={() => miniPlayerStore.prev()}
        disabled={idle || state.chunks_sorted.length === 0}
        aria-label={t("meeting.detail.audioPlayer.prev")}
        className="rounded-md border border-(--color-border) p-1.5 text-(--color-muted-foreground) hover:text-(--color-foreground) disabled:opacity-40"
      >
        <ChevronLeft className="size-4" aria-hidden />
      </button>

      <button
        type="button"
        data-testid="mini-player-play-toggle"
        onClick={() => miniPlayerStore.togglePlay()}
        disabled={idle}
        aria-label={
          state.is_playing
            ? t("meeting.detail.audioPlayer.pause")
            : t("meeting.detail.audioPlayer.play")
        }
        className="rounded-md border border-(--color-border) bg-(--color-card) p-1.5 text-(--color-foreground) hover:bg-(--color-primary)/10 disabled:opacity-40"
      >
        {state.is_playing ? (
          <Pause className="size-4" aria-hidden />
        ) : (
          <Play className="size-4" aria-hidden />
        )}
      </button>

      <button
        type="button"
        data-testid="mini-player-next"
        onClick={() => miniPlayerStore.next()}
        disabled={idle || state.chunks_sorted.length === 0}
        aria-label={t("meeting.detail.audioPlayer.next")}
        className="rounded-md border border-(--color-border) p-1.5 text-(--color-muted-foreground) hover:text-(--color-foreground) disabled:opacity-40"
      >
        <ChevronRight className="size-4" aria-hidden />
      </button>

      {/* Seek bar + current / duration readout */}
      <div className="ml-2 flex flex-1 items-center gap-2 text-xs text-(--color-muted-foreground)">
        <span data-testid="mini-player-current-time" className="font-mono">
          {fmt(currentTime)}
        </span>
        <input
          type="range"
          data-testid="mini-player-seek-bar"
          min={0}
          max={Number.isFinite(duration) && duration > 0 ? duration : 0}
          step={0.1}
          value={currentTime}
          disabled={idle || !duration}
          onChange={(e) => {
            const next = Number.parseFloat(e.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setCurrentTime(next);
          }}
          aria-label={t("meeting.detail.audioPlayer.seekBar")}
          className="flex-1 accent-(--color-primary) disabled:opacity-40"
        />
        <span data-testid="mini-player-duration" className="font-mono">
          {fmt(duration)}
        </span>
      </div>

      <label className="flex items-center gap-1 text-xs text-(--color-muted-foreground)">
        {t("meeting.detail.audioPlayer.speed")}
        <select
          data-testid="mini-player-speed"
          value={state.playback_rate}
          onChange={(e) =>
            miniPlayerStore.setRate(Number.parseFloat(e.target.value) as PlaybackRate)
          }
          className="rounded-md border border-(--color-border) bg-(--color-card) px-1.5 py-0.5 text-xs"
        >
          {PLAYBACK_RATES.map((rate) => (
            <option key={rate} value={rate}>
              {rate}×
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
