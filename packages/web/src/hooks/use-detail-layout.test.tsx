/**
 * useDetailLayout — slice-07 layout preference hook.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, renderHook } from "@testing-library/react";

import { useDetailLayout } from "./use-detail-layout";

const STORAGE_KEY = "meeting-detail.layout";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("useDetailLayout", () => {
  test("defaults to columns when localStorage is unset", () => {
    const { result } = renderHook(() => useDetailLayout());
    expect(result.current[0]).toBe("columns");
  });

  test("invalid stored value falls back to columns", () => {
    window.localStorage.setItem(STORAGE_KEY, "weird-value");
    const { result } = renderHook(() => useDetailLayout());
    expect(result.current[0]).toBe("columns");
  });

  test("setLayout writes to localStorage and updates state", () => {
    const { result } = renderHook(() => useDetailLayout());
    expect(result.current[0]).toBe("columns");

    act(() => {
      result.current[1]("stack");
    });

    expect(result.current[0]).toBe("stack");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("stack");
  });

  test("re-mounting reads the stored value", () => {
    window.localStorage.setItem(STORAGE_KEY, "stack");
    const { result } = renderHook(() => useDetailLayout());
    expect(result.current[0]).toBe("stack");
  });
});
