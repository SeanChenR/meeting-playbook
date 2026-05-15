/**
 * Transcript color preference hook — slice-16 task 6.2.
 *
 * `useSyncExternalStore` wraps `localStorage["meeting-playbook:transcript-color-pref"]`
 * so React components re-render when the user picks a new scheme or an
 * override changes. Writes happen via the setter API; cross-tab sync is
 * triggered by the browser's native `storage` event.
 *
 * The hook is intentionally tiny — heavy lifting (palette math,
 * fail-soft parsing) lives in `lib/transcript-color-schemes.ts` so the
 * hook itself can be tested without DOM mocks.
 */

import { useCallback, useSyncExternalStore } from "react";

import {
  type SchemeId,
  type TranscriptColorPref,
  parseTranscriptColorPref,
} from "../lib/transcript-color-schemes";

const STORAGE_KEY = "meeting-playbook:transcript-color-pref";
const SAME_TAB_EVENT = "meeting-playbook:transcript-color-pref-change";

function _readPref(): TranscriptColorPref {
  if (typeof window === "undefined") return { scheme: "default", overrides: {} };
  return parseTranscriptColorPref(window.localStorage.getItem(STORAGE_KEY));
}

function _writePref(next: TranscriptColorPref): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  // The `storage` event only fires on OTHER tabs. Dispatch a custom
  // event so the writing tab also re-renders its subscribers.
  window.dispatchEvent(new CustomEvent(SAME_TAB_EVENT));
}

function _subscribe(callback: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handler = (e: StorageEvent | Event) => {
    if (e instanceof StorageEvent && e.key !== STORAGE_KEY) return;
    callback();
  };
  window.addEventListener("storage", handler);
  window.addEventListener(SAME_TAB_EVENT, handler);
  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener(SAME_TAB_EVENT, handler);
  };
}

export interface UseTranscriptColorPrefValue {
  pref: TranscriptColorPref;
  setScheme: (id: SchemeId) => void;
  setOverride: (clusterN: number, hue: number) => void;
  resetOverride: (clusterN: number) => void;
}

export function useTranscriptColorPref(): UseTranscriptColorPrefValue {
  // The getSnapshot must return a stable reference when the underlying
  // data hasn't changed. We compute a JSON string snapshot, but return
  // the parsed object — React's compare uses ===, so we cache via a
  // closure that compares the raw string.
  const pref = useSyncExternalStore(
    _subscribe,
    () => JSON.stringify(_readPref()),
    () => JSON.stringify({ scheme: "default", overrides: {} }),
  );
  const parsed = JSON.parse(pref) as TranscriptColorPref;

  const setScheme = useCallback((id: SchemeId) => {
    const current = _readPref();
    _writePref({ ...current, scheme: id });
  }, []);

  const setOverride = useCallback((clusterN: number, hue: number) => {
    const current = _readPref();
    _writePref({
      ...current,
      overrides: { ...current.overrides, [clusterN]: hue },
    });
  }, []);

  const resetOverride = useCallback((clusterN: number) => {
    const current = _readPref();
    const next: Record<number, number> = { ...current.overrides };
    delete next[clusterN];
    _writePref({ ...current, overrides: next });
  }, []);

  return { pref: parsed, setScheme, setOverride, resetOverride };
}
