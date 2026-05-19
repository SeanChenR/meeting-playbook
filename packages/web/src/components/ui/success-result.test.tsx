/**
 * SuccessResult tests — ui-overhaul-animated-surfaces task 6.5.
 *
 * Adopted from `ui.devsloka.in` success-result. Single-shot per mount.
 * Reduced motion → final frame appears immediately, `onAnimationComplete`
 * fires on the next tick.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { SuccessResult } from "./success-result";

beforeEach(() => {
  // @ts-expect-error happy-dom override
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(cleanup);

describe("SuccessResult", () => {
  test("renders the message + a check glyph", () => {
    render(<SuccessResult message="Uploaded" />);
    expect(screen.getByText("Uploaded")).toBeDefined();
    expect(screen.getByTestId("success-result-check")).toBeDefined();
  });

  test("under reduced motion, the check appears with data-reduced-motion=true", async () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(<SuccessResult message="Done" />);
    const root = screen.getByTestId("success-result");
    expect(root.getAttribute("data-reduced-motion")).toBe("true");
  });

  test("onAnimationComplete fires under reduced motion within one tick", async () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    let called = false;
    render(<SuccessResult message="Done" onAnimationComplete={() => (called = true)} />);
    await waitFor(() => expect(called).toBe(true));
  });

  test("no raw hex literals in className", () => {
    render(<SuccessResult message="Done" />);
    const root = screen.getByTestId("success-result");
    expect(/#[0-9a-fA-F]{3,8}/.test(root.className)).toBe(false);
  });
});
