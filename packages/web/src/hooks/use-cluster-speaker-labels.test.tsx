/**
 * Tests for useClusterSpeakerLabels — slice-16 task 10.3.
 *
 * Four scenarios:
 *   (a) empty localStorage → empty labels
 *   (b) setLabel writes through + re-render
 *   (c) invalid label (empty / too long / non-string) → fail-soft, no write
 *   (d) cross-tab storage event triggers re-render
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, renderHook } from "@testing-library/react";

import { useClusterSpeakerLabels } from "./use-cluster-speaker-labels";

const STORAGE_KEY = "meeting-playbook:speaker-labels";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("useClusterSpeakerLabels", () => {
  test("(a) empty localStorage → empty labels", () => {
    const { result } = renderHook(() => useClusterSpeakerLabels("m1"));
    expect(result.current.labels).toEqual({});
  });

  test("(b) setLabel writes through and re-renders", () => {
    const { result } = renderHook(() => useClusterSpeakerLabels("m1"));
    act(() => {
      result.current.setLabel(2, "Alice");
    });
    expect(result.current.labels[2]).toBe("Alice");
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.m1[2]).toBe("Alice");
  });

  test("(c) invalid labels are fail-soft rejected", () => {
    const { result } = renderHook(() => useClusterSpeakerLabels("m1"));
    act(() => {
      result.current.setLabel(1, ""); // empty
      result.current.setLabel(1, "   "); // whitespace
      result.current.setLabel(1, "x".repeat(51)); // too long
    });
    expect(result.current.labels[1]).toBeUndefined();
    const raw = window.localStorage.getItem(STORAGE_KEY);
    // localStorage may have been touched, but no entry for cluster 1.
    if (raw) {
      const stored = JSON.parse(raw);
      expect(stored.m1?.[1]).toBeUndefined();
    }
  });

  test("(d) resetLabel removes one cluster but preserves siblings", () => {
    const { result } = renderHook(() => useClusterSpeakerLabels("m1"));
    act(() => {
      result.current.setLabel(1, "Alice");
      result.current.setLabel(2, "Bob");
    });
    act(() => {
      result.current.resetLabel(1);
    });
    expect(result.current.labels[1]).toBeUndefined();
    expect(result.current.labels[2]).toBe("Bob");
  });

  test("(e) cross-tab storage event triggers re-render", () => {
    const { result } = renderHook(() => useClusterSpeakerLabels("m1"));
    act(() => {
      const payload = JSON.stringify({ m1: { 3: "Carol" } });
      window.localStorage.setItem(STORAGE_KEY, payload);
      window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY, newValue: payload }));
    });
    expect(result.current.labels[3]).toBe("Carol");
  });

  test("(f) labels are scoped to meetingId", () => {
    const { result: r1 } = renderHook(() => useClusterSpeakerLabels("m1"));
    act(() => {
      r1.current.setLabel(2, "Alice");
    });
    const { result: r2 } = renderHook(() => useClusterSpeakerLabels("m2"));
    expect(r2.current.labels[2]).toBeUndefined();
  });
});
