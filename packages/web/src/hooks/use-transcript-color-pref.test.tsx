/**
 * Tests for useTranscriptColorPref — slice-16 task 6.2.
 *
 * Five scenarios:
 *   (a) empty localStorage → default pref
 *   (b) setScheme writes through + state updates
 *   (c) setOverride writes through + state updates
 *   (d) resetOverride removes the entry
 *   (e) cross-tab storage event triggers re-render with new value
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, renderHook } from "@testing-library/react";

import { useTranscriptColorPref } from "./use-transcript-color-pref";

const STORAGE_KEY = "meeting-playbook:transcript-color-pref";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("useTranscriptColorPref", () => {
  test("(a) empty localStorage → default scheme + empty overrides", () => {
    const { result } = renderHook(() => useTranscriptColorPref());
    expect(result.current.pref.scheme).toBe("default");
    expect(result.current.pref.overrides).toEqual({});
  });

  test("(b) setScheme writes through and re-renders with new value", () => {
    const { result } = renderHook(() => useTranscriptColorPref());
    act(() => {
      result.current.setScheme("vivid");
    });
    expect(result.current.pref.scheme).toBe("vivid");
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.scheme).toBe("vivid");
  });

  test("(c) setOverride writes through and re-renders", () => {
    const { result } = renderHook(() => useTranscriptColorPref());
    act(() => {
      result.current.setOverride(2, 120);
    });
    expect(result.current.pref.overrides[2]).toBe(120);
  });

  test("(d) resetOverride removes the cluster's entry but keeps others", () => {
    const { result } = renderHook(() => useTranscriptColorPref());
    act(() => {
      result.current.setOverride(1, 180);
      result.current.setOverride(2, 240);
    });
    act(() => {
      result.current.resetOverride(2);
    });
    expect(result.current.pref.overrides[1]).toBe(180);
    expect(result.current.pref.overrides[2]).toBeUndefined();
  });

  test("(e) cross-tab storage event triggers re-render", () => {
    const { result } = renderHook(() => useTranscriptColorPref());
    act(() => {
      // Simulate another tab writing to localStorage.
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ scheme: "pastel", overrides: { 3: 90 } }),
      );
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: STORAGE_KEY,
          newValue: JSON.stringify({ scheme: "pastel", overrides: { 3: 90 } }),
        }),
      );
    });
    expect(result.current.pref.scheme).toBe("pastel");
    expect(result.current.pref.overrides[3]).toBe(90);
  });
});
