/**
 * LocaleToggle component tests — extended for slice ui-overhaul-claude-design
 * task 2.3 (shadcn DropdownMenu rewrite).
 *
 * Verifies:
 *  - Trigger renders the current locale code (zh-TW by default)
 *  - Opening the menu reveals both zh-TW + EN options
 *  - Selecting EN calls i18n.changeLanguage and persists to localStorage
 *  - Selecting the active locale is a no-op
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

  test("trigger renders the current locale code (zh-TW)", () => {
    render(<LocaleToggle />);
    const trigger = screen.getByTestId("locale-toggle");
    expect(trigger.textContent).toContain("zh-TW");
  });

  test("opening the dropdown reveals both zh-TW and EN options", async () => {
    const user = userEvent.setup();
    render(<LocaleToggle />);
    await user.click(screen.getByTestId("locale-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("locale-option-zh-TW")).toBeDefined();
      expect(screen.getByTestId("locale-option-en")).toBeDefined();
    });
  });

  test("selecting EN switches the language and persists to localStorage", async () => {
    const user = userEvent.setup();
    render(<LocaleToggle />);

    await user.click(screen.getByTestId("locale-toggle"));
    const enOption = await screen.findByTestId("locale-option-en");
    await user.click(enOption);

    await waitFor(() => {
      expect(i18n.language).toBe("en");
    });
    expect(localStorage.getItem(LS_KEY)).toBe("en");
  });

  test("selecting the active locale is a no-op", async () => {
    const user = userEvent.setup();
    render(<LocaleToggle />);

    await user.click(screen.getByTestId("locale-toggle"));
    const zhOption = await screen.findByTestId("locale-option-zh-TW");
    await user.click(zhOption);

    expect(i18n.language).toBe("zh-TW");
    expect(localStorage.getItem(LS_KEY)).toBe("zh-TW");
  });
});
