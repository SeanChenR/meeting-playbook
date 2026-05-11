/**
 * AuthShell tests — slice ui-overhaul-claude-design task 2.2.
 *
 * Covers:
 *   - ThemeToggle renders in the top-right toolbar (absolute right-4 top-4)
 *   - Children render inside the centered main scaffold (justify-center)
 *   - LocaleToggle still present alongside ThemeToggle
 *
 * Wraps render() in ThemeProvider because AuthShell now uses ThemeToggle
 * which calls useTheme().
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { type ReactNode } from "react";

import { ThemeProvider } from "../lib/theme-provider";
import { AuthShell } from "./auth-shell";

beforeEach(() => {
  // happy-dom needs matchMedia stub so ThemeProvider initialises cleanly.
  // @ts-expect-error — overriding for tests
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

function _withTheme(ui: ReactNode) {
  return <ThemeProvider initialTheme="light">{ui}</ThemeProvider>;
}

describe("AuthShell toolbar", () => {
  test("renders theme-toggle in the absolute top-right toolbar", () => {
    render(
      _withTheme(
        <AuthShell>
          <div data-testid="child" />
        </AuthShell>,
      ),
    );
    const toolbar = screen.getByTestId("auth-shell-toolbar");
    expect(toolbar.className).toContain("absolute");
    expect(toolbar.className).toContain("right-4");
    expect(toolbar.className).toContain("top-4");

    const themeToggle = screen.getByTestId("theme-toggle");
    expect(themeToggle).toBeDefined();
    // Theme toggle must be a descendant of the toolbar (not somewhere else).
    expect(toolbar.contains(themeToggle)).toBe(true);
  });

  test("toolbar also contains the locale toggle", () => {
    render(
      _withTheme(
        <AuthShell>
          <div />
        </AuthShell>,
      ),
    );
    const toolbar = screen.getByTestId("auth-shell-toolbar");
    // LocaleToggle exposes data-testid="locale-toggle".
    const localeToggle = screen.getByTestId("locale-toggle");
    expect(toolbar.contains(localeToggle)).toBe(true);
  });
});

describe("AuthShell layout", () => {
  test("centers children inside the main scaffold (justify-center)", () => {
    render(
      _withTheme(
        <AuthShell>
          <div data-testid="child">hello</div>
        </AuthShell>,
      ),
    );
    const main = screen.getByTestId("auth-shell-main");
    expect(main.className).toContain("justify-center");
    expect(main.className).toContain("min-h-dvh");

    const child = screen.getByTestId("child");
    // Child must live inside the centered main scaffold.
    expect(main.contains(child)).toBe(true);
  });
});
