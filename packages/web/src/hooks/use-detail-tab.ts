/**
 * useDetailTab — slice-10 detail-page tab state, persisted per meeting.
 *
 * Per design.md Decision 6:
 * - Default tab is `workspace`
 * - Persisted to localStorage keyed `meeting-detail-tab:{meetingId}`
 * - When the persisted value is `summary` but the meeting is not yet
 *   `completed`, fall back to `workspace` (avoid landing on a disabled tab)
 */

import { useCallback, useEffect, useState } from "react";

export type DetailTab = "workspace" | "summary";

interface MinimalMeeting {
  status: string;
}

const _PREFIX = "meeting-detail-tab:";

function _keyFor(meetingId: string): string {
  return `${_PREFIX}${meetingId}`;
}

function _readPersisted(meetingId: string): DetailTab | null {
  try {
    const v = localStorage.getItem(_keyFor(meetingId));
    if (v === "workspace" || v === "summary") return v;
    return null;
  } catch {
    return null;
  }
}

function _writePersisted(meetingId: string, tab: DetailTab): void {
  try {
    localStorage.setItem(_keyFor(meetingId), tab);
  } catch {
    // localStorage might be unavailable (private browsing, quota); silent.
  }
}

export function useDetailTab(
  meetingId: string,
  meeting: MinimalMeeting | null,
): readonly [DetailTab, (next: DetailTab) => void] {
  const [tab, setTabState] = useState<DetailTab>(() => {
    const persisted = _readPersisted(meetingId);
    if (persisted === "summary") {
      // Fall back to workspace if the meeting isn't completed yet.
      if (!meeting || meeting.status !== "completed") return "workspace";
    }
    return persisted ?? "workspace";
  });

  // If meeting status changes (in_progress → completed) between renders
  // and the user previously set summary as their preferred tab, honor
  // that on the first opportunity.
  useEffect(() => {
    const persisted = _readPersisted(meetingId);
    if (persisted === "summary" && meeting?.status === "completed" && tab !== "summary") {
      setTabState("summary");
    }
  }, [meeting?.status, meetingId, tab]);

  const setTab = useCallback(
    (next: DetailTab) => {
      setTabState(next);
      _writePersisted(meetingId, next);
    },
    [meetingId],
  );

  return [tab, setTab] as const;
}
