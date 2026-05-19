/**
 * Stars background tests — ui-overhaul-animated-surfaces task 2.1.
 *
 * Four gate combinations:
 *   - dark + motion allowed → renders canvas/svg sibling
 *   - dark + reduced motion → null
 *   - light + motion allowed → null
 *   - public route (no ThemeProvider needed) → null
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { ThemeProvider } from "../../../lib/theme-provider";
import { Stars } from "./stars";

beforeEach(() => {
  // Default: motion allowed.
  // @ts-expect-error happy-dom override
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(cleanup);

describe("Stars background", () => {
  test("renders in dark mode with motion allowed (protected route)", () => {
    render(
      <ThemeProvider initialTheme="dark">
        <Stars />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("stars-layer")).toBeDefined();
  });

  test("returns null in light mode", () => {
    render(
      <ThemeProvider initialTheme="light">
        <Stars />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("stars-layer")).toBeNull();
  });

  test("returns null when prefers-reduced-motion: reduce matches", () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(
      <ThemeProvider initialTheme="dark">
        <Stars />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("stars-layer")).toBeNull();
  });

  test("returns null when route prop is public", () => {
    render(
      <ThemeProvider initialTheme="dark">
        <Stars route="public" />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("stars-layer")).toBeNull();
  });

  test("renders a bounded star count (≤ 200)", () => {
    render(
      <ThemeProvider initialTheme="dark">
        <Stars />
      </ThemeProvider>,
    );
    const layer = screen.getByTestId("stars-layer");
    const stars = layer.querySelectorAll('[data-testid="star"]');
    // Density bumped from 60 to 120 during UI overhaul follow-up so the
    // layer reads on a 1080p+ canvas; cap stays defensive to bound paint cost.
    expect(stars.length).toBeGreaterThan(0);
    expect(stars.length).toBeLessThanOrEqual(200);
  });

  test("uses Aura tokens (no raw hex literals)", () => {
    render(
      <ThemeProvider initialTheme="dark">
        <Stars />
      </ThemeProvider>,
    );
    const layer = screen.getByTestId("stars-layer");
    const html = layer.outerHTML;
    expect(/#[0-9a-fA-F]{3,8}/.test(html)).toBe(false);
  });
});
