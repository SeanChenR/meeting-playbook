/**
 * useDetailTab — slice-10 detail-page tab state hook tests.
 *
 * Per spec meeting-detail-layout MODIFIED requirement scenarios:
 * - default = workspace when no persisted value
 * - persisted summary falls back to workspace if meeting is not completed
 * - setTab(summary) persists to localStorage when meeting is completed
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, renderHook } from "@testing-library/react";
import { useDetailTab } from "./use-detail-tab";

const _SCHEDULED = { status: "scheduled" };
const _COMPLETED = { status: "completed" };

beforeEach(() => {
  // Reset between tests so persisted state doesn't leak.
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("useDetailTab", () => {
  test("default is workspace when no persisted value", () => {
    const { result } = renderHook(() => useDetailTab("m_x", _SCHEDULED));
    expect(result.current[0]).toBe("workspace");
  });

  test("persisted summary falls back to workspace when meeting not completed", () => {
    localStorage.setItem("meeting-detail-tab:m_x", "summary");
    const { result } = renderHook(() => useDetailTab("m_x", { status: "in_progress" }));
    expect(result.current[0]).toBe("workspace");
  });

  test("persisted summary is honored when meeting is completed", () => {
    localStorage.setItem("meeting-detail-tab:m_x", "summary");
    const { result } = renderHook(() => useDetailTab("m_x", _COMPLETED));
    expect(result.current[0]).toBe("summary");
  });

  test("setTab(summary) persists to localStorage when meeting completed", () => {
    const { result } = renderHook(() => useDetailTab("m_x", _COMPLETED));
    expect(result.current[0]).toBe("workspace");
    act(() => {
      result.current[1]("summary");
    });
    expect(result.current[0]).toBe("summary");
    expect(localStorage.getItem("meeting-detail-tab:m_x")).toBe("summary");
  });

  test("setTab(workspace) overwrites persisted summary value", () => {
    localStorage.setItem("meeting-detail-tab:m_x", "summary");
    const { result } = renderHook(() => useDetailTab("m_x", _COMPLETED));
    act(() => {
      result.current[1]("workspace");
    });
    expect(result.current[0]).toBe("workspace");
    expect(localStorage.getItem("meeting-detail-tab:m_x")).toBe("workspace");
  });

  test("persisted state is keyed per meeting id (no leak between meetings)", () => {
    localStorage.setItem("meeting-detail-tab:m_a", "summary");
    const { result: a } = renderHook(() => useDetailTab("m_a", _COMPLETED));
    const { result: b } = renderHook(() => useDetailTab("m_b", _COMPLETED));
    expect(a.current[0]).toBe("summary");
    expect(b.current[0]).toBe("workspace"); // separate key
  });
});
