/**
 * useDetailLayout — read/write the detail page layout preference (slice-07).
 *
 * Persisted in localStorage under the key `meeting-detail.layout`. Default
 * is `"columns"`; invalid stored values fall back to the default. The hook
 * keeps its own React state in sync with localStorage so the UI updates
 * immediately on toggle (no reload required).
 *
 * Per design.md (`Detail page layout switcher: localStorage-persisted Stack/Columns`).
 */

import { useCallback, useEffect, useState } from "react";

export type DetailLayout = "stack" | "columns";

const STORAGE_KEY = "meeting-detail.layout";
const DEFAULT_LAYOUT: DetailLayout = "columns";

function _readStored(): DetailLayout {
  if (typeof window === "undefined") return DEFAULT_LAYOUT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "stack" || raw === "columns") return raw;
    return DEFAULT_LAYOUT;
  } catch {
    return DEFAULT_LAYOUT;
  }
}

export function useDetailLayout(): [DetailLayout, (next: DetailLayout) => void] {
  const [layout, setLayoutState] = useState<DetailLayout>(_readStored);

  // Initialise from storage exactly once after mount (handles SSR/Vite where
  // _readStored returned default during render).
  useEffect(() => {
    const stored = _readStored();
    setLayoutState(stored);
  }, []);

  const setLayout = useCallback((next: DetailLayout) => {
    setLayoutState(next);
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Quota / privacy mode: silently fall back to in-memory state only.
    }
  }, []);

  return [layout, setLayout];
}
