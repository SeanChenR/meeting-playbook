/**
 * ThemeToggle tests — ui-overhaul-primitive-upgrade task 7 (Decision 4).
 *
 * Two-state toggle (dark ↔ light); `system` is still honoured at fresh-load
 * via ThemeProvider's matchMedia detection but the UI no longer surfaces
 * a system entry.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider } from "../lib/theme-provider";
import { ThemeToggle } from "./theme-toggle";

beforeEach(() => {
  // @ts-expect-error — overriding for tests
  window.matchMedia = (_q: string) => ({
    matches: false,
    media: _q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(cleanup);

describe("ThemeToggle", () => {
  test("renders the trigger button", () => {
    render(
      <ThemeProvider initialTheme="light">
        <ThemeToggle />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme-toggle")).toBeDefined();
  });

  test("first click on light flips to dark + persists", async () => {
    render(
      <ThemeProvider initialTheme="light">
        <ThemeToggle />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId("theme-toggle"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("mp-theme")).toBe("dark");
  });

  test("second click flips back to light", async () => {
    render(
      <ThemeProvider initialTheme="dark">
        <ThemeToggle />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId("theme-toggle"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem("mp-theme")).toBe("light");
  });

  test("toggle never writes 'system' to localStorage", async () => {
    render(
      <ThemeProvider initialTheme="dark">
        <ThemeToggle />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId("theme-toggle"));
    expect(window.localStorage.getItem("mp-theme")).not.toBe("system");
  });
});
