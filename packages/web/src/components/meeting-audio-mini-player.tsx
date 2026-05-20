/**
 * MeetingAudioMiniPlayer — slice-16 task 10.7 (whole-recording rewrite),
 * slice-25 task 4.1 + 4.2 (source toggle + mix-failure inline error).
 *
 * Sticky-bottom bar mounted from the meeting detail route. Dual-channel
 * meetings expose a `mixed / 我方 / 對方` source toggle (defaulting to
 * mixed — per design D6 / D11). Single-channel meetings hide the toggle
 * and play the single recording directly.
 *
 * Switching the toggle reloads `<audio>.src` to the new source URL while
 * preserving `currentTime`, `paused`, and `playbackRate` (per design D5).
 * Mix endpoint errors (`recording.mixed_not_applicable`,
 * `recording.mix_failed`) surface as an inline alert; the toggle does NOT
 * auto-switch sources (per design D9).
 */

import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  PLAYBACK_RATES,
  type PlaybackRate,
  type SourceKey,
  miniPlayerStore,
  pickPlaybackSources,
  useMiniPlayerStore,
} from "../hooks/use-mini-player";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { Alert } from "./ui/alert";
import { GlassDock } from "./ui/glass-dock";

export interface MeetingAudioMiniPlayerProps {
  meetingId: string;
}

const SOURCE_STORAGE_KEY = "miniPlayerSource";

function _readPersistedSource(defaultSource: SourceKey): SourceKey {
  if (typeof window === "undefined") return defaultSource;
  const raw = window.localStorage.getItem(SOURCE_STORAGE_KEY);
  if (raw === "mixed" || raw === "me" || raw === "counterparty") return raw;
  return defaultSource;
}

export function MeetingAudioMiniPlayer({ meetingId }: MeetingAudioMiniPlayerProps) {
  const { t } = useTranslation();
  const state = useMiniPlayerStore();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const playback = useMemo(
    () => pickPlaybackSources(meetingId, state.recordings),
    [meetingId, state.recordings],
  );

  // `currentSource` is initialized once from localStorage; the toggle handler
  // updates both state + storage. Falls back to `playback.defaultSource` when
  // the persisted key is absent or invalid (per spec scenario "Toggle persists
  // across page reload").
  const [currentSource, setCurrentSource] = useState<SourceKey>(() =>
    _readPersistedSource(playback.defaultSource),
  );

  // If the persisted source isn't available for THIS meeting (e.g. user
  // previously chose "them" but landed on a single-channel meeting), snap to
  // the default so we don't render an empty `<audio>` src.
  const effectiveSource: SourceKey =
    playback.sources[currentSource] !== undefined ? currentSource : playback.defaultSource;

  const audioSrc = playback.sources[effectiveSource] ?? null;

  // ─── Mix-failure detection (task 4.2) ────────────────────────────────
  // Per design D9, we don't silently fall back to me-only when the mixed
  // endpoint fails — we surface the error so the user knows the mixed audio
  // is unavailable and must manually pick `me` / `counterparty`.
  const [mixErrorCode, setMixErrorCode] = useState<string | null>(null);
  useEffect(() => {
    if (effectiveSource !== "mixed" || !audioSrc) {
      setMixErrorCode(null);
      return;
    }
    let cancelled = false;
    // Probe with a single-byte Range — backend returns the envelope body
    // for 404 / 500; `<audio>` itself only surfaces a generic MEDIA_ERROR.
    fetch(audioSrc, { headers: { Range: "bytes=0-0" } })
      .then(async (resp) => {
        if (cancelled) return;
        if (resp.ok) {
          setMixErrorCode(null);
          return;
        }
        try {
          const body = (await resp.json()) as { error_code?: string };
          setMixErrorCode(body.error_code ?? "common.unknown");
        } catch {
          setMixErrorCode("common.unknown");
        }
      })
      .catch(() => {
        if (!cancelled) setMixErrorCode("common.unknown");
      });
    return () => {
      cancelled = true;
    };
  }, [audioSrc, effectiveSource]);

  // ─── Source-toggle handler with currentTime / paused preservation ────
  function _handleSourceChange(next: SourceKey) {
    if (next === currentSource) return;
    if (playback.sources[next] === undefined) return;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SOURCE_STORAGE_KEY, next);
    }
    setCurrentSource(next);
    // currentTime / paused are restored by onLoadedMetadata + the existing
    // play/pause effect below — both read from `state` / `audioRef`.
  }

  // Preserve currentTime across src changes (toggle).
  const pendingSeekRef = useRef<number | null>(null);
  useEffect(() => {
    if (audioRef.current) {
      pendingSeekRef.current = audioRef.current.currentTime || null;
    }
  }, [audioSrc]);

  // Keep <audio>.playbackRate in sync with store.
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = state.playback_rate;
    }
  }, [state.playback_rate, audioSrc]);

  // Apply seek_target_seconds (chunk navigation) when it changes.
  useEffect(() => {
    if (state.seek_target_seconds === null) return;
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = state.seek_target_seconds;
    miniPlayerStore.ackSeek();
  }, [state.seek_target_seconds, state.seek_token]);

  // Drive play / pause from store (re-fires when src changes).
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

  const sourceButtons: ReadonlyArray<{ key: SourceKey; label: string; testid: string }> = [
    { key: "mixed", label: t("meeting.detail.audioPlayer.source.mixed"), testid: "source-mixed" },
    { key: "me", label: t("meeting.detail.audioPlayer.source.me"), testid: "source-me" },
    {
      key: "counterparty",
      label: t("meeting.detail.audioPlayer.source.counterparty"),
      testid: "source-counterparty",
    },
  ];

  return (
    <GlassDock
      data-testid="meeting-audio-mini-player"
      className="sticky bottom-0 z-30 flex flex-col gap-2 border-t px-4 py-2"
    >
      {mixErrorCode && (
        <Alert data-testid="mini-player-mix-error" variant="destructive">
          {localizedErrorMessage(mixErrorCode, t)}
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {audioSrc && (
          <audio
            ref={audioRef}
            data-testid="mini-player-audio"
            src={audioSrc}
            preload="metadata"
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => {
              setDuration(e.currentTarget.duration);
              if (pendingSeekRef.current !== null) {
                e.currentTarget.currentTime = pendingSeekRef.current;
                pendingSeekRef.current = null;
              }
            }}
            onEnded={() => miniPlayerStore.pause()}
          />
        )}

        <button
          type="button"
          data-testid="mini-player-prev"
          onClick={() => miniPlayerStore.prev()}
          disabled={idle || state.chunks_sorted.length === 0}
          aria-label={t("meeting.detail.audioPlayer.prev")}
          className="inline-flex size-8 items-center justify-center rounded-full bg-(--color-primary)/10 text-(--color-primary) ring-1 ring-(--color-primary)/15 transition-colors hover:bg-(--color-primary)/18 disabled:opacity-40"
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
          className="inline-flex size-9 items-center justify-center rounded-full bg-(--color-primary) text-(--color-primary-foreground) shadow-(--shadow-sm) transition-all hover:bg-(--color-primary-hover) hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
        >
          {state.is_playing ? (
            <Pause className="size-4" aria-hidden />
          ) : (
            <Play className="size-4 translate-x-px" aria-hidden />
          )}
        </button>

        <button
          type="button"
          data-testid="mini-player-next"
          onClick={() => miniPlayerStore.next()}
          disabled={idle || state.chunks_sorted.length === 0}
          aria-label={t("meeting.detail.audioPlayer.next")}
          className="inline-flex size-8 items-center justify-center rounded-full bg-(--color-primary)/10 text-(--color-primary) ring-1 ring-(--color-primary)/15 transition-colors hover:bg-(--color-primary)/18 disabled:opacity-40"
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

        {/* Source toggle — dual-channel meetings only. */}
        {playback.kind === "dual" && (
          <div
            data-testid="mini-player-source-toggle"
            role="group"
            aria-label={t("meeting.detail.audioPlayer.sourceLabel")}
            className="flex items-center gap-0.5 rounded-full bg-(--color-primary)/8 p-0.5 text-xs ring-1 ring-(--color-primary)/15"
          >
            {sourceButtons.map(({ key, label, testid }) => {
              const active = effectiveSource === key;
              return (
                <button
                  key={key}
                  type="button"
                  data-testid={testid}
                  onClick={() => _handleSourceChange(key)}
                  aria-pressed={active}
                  className={
                    active
                      ? "rounded-full bg-(--color-primary) px-2.5 py-1 font-medium text-(--color-primary-foreground) shadow-(--shadow-sm)"
                      : "rounded-full px-2.5 py-1 text-(--color-primary)/70 hover:text-(--color-primary)"
                  }
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}

        <label className="flex items-center gap-1.5 text-xs text-(--color-primary)">
          {t("meeting.detail.audioPlayer.speed")}
          <select
            data-testid="mini-player-speed"
            value={state.playback_rate}
            onChange={(e) =>
              miniPlayerStore.setRate(Number.parseFloat(e.target.value) as PlaybackRate)
            }
            className="rounded-full bg-(--color-primary)/8 px-2 py-0.5 text-xs font-medium text-(--color-primary) ring-1 ring-(--color-primary)/15 transition-colors hover:bg-(--color-primary)/15 focus:outline-none focus:ring-2 focus:ring-(--color-primary)/35"
          >
            {PLAYBACK_RATES.map((rate) => (
              <option key={rate} value={rate}>
                {rate}×
              </option>
            ))}
          </select>
        </label>
      </div>
    </GlassDock>
  );
}
