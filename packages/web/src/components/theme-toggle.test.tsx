/**
 * ThemeToggle tests — slice ui-overhaul-claude-design task 1.4.
 *
 * Three cases per task description:
 *   - render
 *   - clicking dark → setTheme("dark")
 *   - clicking system → setTheme("system")
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider } from "../lib/theme-provider";
import { ThemeToggle } from "./theme-toggle";

beforeEach(() => {
  // Stub matchMedia so happy-dom doesn't blow up inside ThemeProvider.
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

  test("clicking 'dark' sets theme=dark and flips data-theme", async () => {
    render(
      <ThemeProvider initialTheme="light">
        <ThemeToggle />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId("theme-toggle"));
    await userEvent.click(await screen.findByTestId("theme-option-dark"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("mp-theme")).toBe("dark");
  });

  test("clicking 'system' sets theme=system and resolves against matchMedia", async () => {
    render(
      <ThemeProvider initialTheme="dark">
        <ThemeToggle />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId("theme-toggle"));
    await userEvent.click(await screen.findByTestId("theme-option-system"));
    // matchMedia stub returns matches:false → system resolves to light
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem("mp-theme")).toBe("system");
  });
});
