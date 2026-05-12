/**
 * AnimateIcon wrapper smoke — slice animate-ui-icons-swap task 1.4.
 *
 * The wrapper exposes `AnimateIcon` (root) + per-call-site
 * `IconWrapper` factories. Tests here mount a minimal icon-shaped
 * component routed through the wrapper and assert:
 *   - An <svg> root renders
 *   - The wrapper does not throw on default props (no triggers set)
 *
 * Per-icon hover / loop behaviours are covered by the individual icon
 * smoke tests + the call-site tests (Phase 3 tasks).
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render } from "@testing-library/react";

import { AnimateIcon } from "./icon";

beforeEach(() => {
  // @ts-expect-error — happy-dom stub
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(cleanup);

describe("AnimateIcon wrapper", () => {
  test("mounts with a static <svg> root using default props", () => {
    const { container } = render(
      <AnimateIcon>
        <svg viewBox="0 0 24 24" data-testid="wrapped-svg">
          <path d="M0 0L24 24" />
        </svg>
      </AnimateIcon>,
    );
    expect(container.querySelector("svg")).not.toBeNull();
  });

  test("renders even when prefers-reduced-motion is set (static fallback)", () => {
    // @ts-expect-error — happy-dom stub override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduce"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    expect(() =>
      render(
        <AnimateIcon>
          <svg viewBox="0 0 24 24">
            <path d="M0 0L24 24" />
          </svg>
        </AnimateIcon>,
      ),
    ).not.toThrow();
  });
});
