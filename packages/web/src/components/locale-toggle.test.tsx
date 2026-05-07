/**
 * AC-5 LocaleToggle component tests.
 *
 * Verifies:
 *  - Two language buttons render (繁中 / EN)
 *  - The button matching current i18n.language has aria-pressed="true"
 *  - Clicking the inactive button calls changeLanguage with the right code
 *  - The selection persists to localStorage under the namespaced key
 *  - No page reload happens on switch (DOM stays mounted, localStorage updated)
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { i18n } from "../lib/i18n";
import { LocaleToggle } from "./locale-toggle";

const LS_KEY = "meeting-playbook.locale";

describe("LocaleToggle", () => {
  beforeEach(async () => {
    localStorage.removeItem(LS_KEY);
    await i18n.changeLanguage("zh-TW");
  });
  afterEach(async () => {
    cleanup();
    localStorage.removeItem(LS_KEY);
    await i18n.changeLanguage("zh-TW");
  });

  test("renders both language buttons (zh-TW + en)", () => {
    render(<LocaleToggle />);
    expect(screen.getByRole("button", { name: /繁中/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /^EN$/ })).toBeDefined();
  });

  test("the current language button has aria-pressed='true'", async () => {
    render(<LocaleToggle />);
    const zhBtn = screen.getByRole("button", { name: /繁中/ });
    expect(zhBtn.getAttribute("aria-pressed")).toBe("true");

    const enBtn = screen.getByRole("button", { name: /^EN$/ });
    expect(enBtn.getAttribute("aria-pressed")).toBe("false");
  });

  test("clicking EN switches the language and persists to localStorage", async () => {
    const user = userEvent.setup();
    render(<LocaleToggle />);

    await user.click(screen.getByRole("button", { name: /^EN$/ }));

    await waitFor(() => {
      expect(i18n.language).toBe("en");
    });
    expect(localStorage.getItem(LS_KEY)).toBe("en");
  });

  test("clicking the active button is a no-op (still pressed, no reload)", async () => {
    const user = userEvent.setup();
    render(<LocaleToggle />);

    await user.click(screen.getByRole("button", { name: /繁中/ }));

    expect(i18n.language).toBe("zh-TW");
    expect(localStorage.getItem(LS_KEY)).toBe("zh-TW");
    // DOM still mounted — getBy* would throw if unmounted/reloaded
    expect(screen.getByRole("button", { name: /繁中/ }).getAttribute("aria-pressed")).toBe("true");
  });
});
