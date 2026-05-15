/**
 * Cluster speaker label override hook — slice-16 task 10.3.
 *
 * Lets the user rename "與會者 1" / "Participant 2" / ... to something
 * meaningful per meeting (e.g. "Alice" / "Bob"). The mapping lives in
 * `localStorage["meeting-playbook:speaker-labels"]` with the shape
 *
 *   { [meetingId]: { [clusterN]: label } }
 *
 * so each meeting can have its own roster without leaking labels across
 * meetings. The backend's `transcript_chunk.speaker` column stays a
 * capture-time fact — rename is a UI-side display preference only.
 */

import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "meeting-playbook:speaker-labels";
const SAME_TAB_EVENT = "meeting-playbook:speaker-labels-change";
const MAX_LABEL_LEN = 50;

type LabelMap = Record<string, Record<number, string>>;

function _read(): LabelMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return _sanitize(parsed as Record<string, unknown>);
    }
    return {};
  } catch {
    return {};
  }
}

function _sanitize(raw: Record<string, unknown>): LabelMap {
  const out: LabelMap = {};
  for (const [mid, perMeeting] of Object.entries(raw)) {
    if (!perMeeting || typeof perMeeting !== "object" || Array.isArray(perMeeting)) continue;
    const labels: Record<number, string> = {};
    for (const [k, v] of Object.entries(perMeeting as Record<string, unknown>)) {
      const n = Number.parseInt(k, 10);
      if (Number.isFinite(n) && n >= 1 && _isValidLabel(v)) {
        labels[n] = v as string;
      }
    }
    if (Object.keys(labels).length > 0) out[mid] = labels;
  }
  return out;
}

function _isValidLabel(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const trimmed = value.trim();
  return trimmed.length >= 1 && trimmed.length <= MAX_LABEL_LEN;
}

function _write(next: LabelMap): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
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

export interface UseClusterSpeakerLabelsValue {
  labels: Record<number, string>;
  setLabel: (clusterN: number, label: string) => void;
  resetLabel: (clusterN: number) => void;
}

export function useClusterSpeakerLabels(meetingId: string): UseClusterSpeakerLabelsValue {
  const snapshot = useSyncExternalStore(
    _subscribe,
    () => JSON.stringify(_read()),
    () => "{}",
  );
  const parsed = JSON.parse(snapshot) as LabelMap;
  const labels = parsed[meetingId] ?? {};

  const setLabel = useCallback(
    (clusterN: number, label: string) => {
      if (!_isValidLabel(label)) return; // fail-soft
      if (!Number.isFinite(clusterN) || clusterN < 1) return;
      const current = _read();
      const perMeeting = { ...(current[meetingId] ?? {}), [clusterN]: label.trim() };
      _write({ ...current, [meetingId]: perMeeting });
    },
    [meetingId],
  );

  const resetLabel = useCallback(
    (clusterN: number) => {
      const current = _read();
      const perMeeting = { ...(current[meetingId] ?? {}) };
      delete perMeeting[clusterN];
      if (Object.keys(perMeeting).length === 0) {
        const next = { ...current };
        delete next[meetingId];
        _write(next);
      } else {
        _write({ ...current, [meetingId]: perMeeting });
      }
    },
    [meetingId],
  );

  return { labels, setLabel, resetLabel };
}
