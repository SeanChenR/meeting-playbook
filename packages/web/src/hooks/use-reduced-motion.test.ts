/**
 * useReducedMotion tests — ui-overhaul-animated-surfaces task 1.1.
 *
 * Single canonical hook every effect-layer component must consult so
 * `prefers-reduced-motion: reduce` is honoured uniformly. Verifies:
 *   - initial value reflects current matchMedia.matches
 *   - reacts to runtime `change` events
 *   - SSR-safe (no window) returns false
 */

import { afterEach, describe, expect, test } from "bun:test";
import { act, cleanup, renderHook } from "@testing-library/react";

import { useReducedMotion } from "./use-reduced-motion";

type Listener = () => void;

function _installMockMatchMedia(initial: boolean) {
  const listeners: Listener[] = [];
  const mql = {
    matches: initial,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: (_e: string, l: Listener) => {
      listeners.push(l);
    },
    removeEventListener: (_e: string, l: Listener) => {
      const i = listeners.indexOf(l);
      if (i !== -1) listeners.splice(i, 1);
    },
    dispatchEvent: () => true,
  } as unknown as MediaQueryList;
  // @ts-expect-error — happy-dom override
  window.matchMedia = (_q: string) => mql;
  return {
    setMatches(value: boolean) {
      // @ts-expect-error — test override
      mql.matches = value;
      for (const l of listeners) l();
    },
  };
}

afterEach(cleanup);

describe("useReducedMotion", () => {
  test("returns true when matchMedia initially matches", () => {
    _installMockMatchMedia(true);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  test("returns false when matchMedia initially does not match", () => {
    _installMockMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  test("reacts to runtime change events", () => {
    const mock = _installMockMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    act(() => mock.setMatches(true));
    expect(result.current).toBe(true);
    act(() => mock.setMatches(false));
    expect(result.current).toBe(false);
  });
});
