/**
 * useIsInView smoke — slice animate-ui-icons-swap task 1.2.
 *
 * happy-dom doesn't ship a real IntersectionObserver, so the hook can't
 * fire `inView` deterministically here. We assert the hook mounts, the
 * ref accessor returns a callable, and the default `isInView` short-circuit
 * (no `options.inView`) resolves to `true` — exactly the "no view-gated
 * animation requested" path that all 15 swapped icons hit by default.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { act, cleanup, renderHook } from "@testing-library/react";

import { useIsInView } from "./use-is-in-view";

afterEach(cleanup);

describe("useIsInView", () => {
  test("returns { ref, isInView } with isInView=true when no `inView` gate is set", () => {
    const { result } = renderHook(() => useIsInView<HTMLDivElement>(null, {}));
    act(() => undefined);
    expect(result.current.isInView).toBe(true);
    expect(result.current.ref).toBeDefined();
    expect(result.current.ref.current).toBeNull();
  });

  test("ref is assignable to a DOM node", () => {
    const { result } = renderHook(() => useIsInView<HTMLDivElement>(null, {}));
    const el = document.createElement("div");
    result.current.ref.current = el;
    expect(result.current.ref.current).toBe(el);
  });
});
