/**
 * AC-5 + AC-6 LocaleToggle wired into AuthShell — Phase 6 update.
 *
 * The LocaleToggle was rewritten from a segmented two-button group to a
 * shadcn DropdownMenu (Phase 2 task 2.3). The user flow stays the same:
 *
 *   1. Trigger is reachable from AuthShell (top-right toolbar)
 *   2. Opening the menu and clicking EN flips the rendered subhead AND
 *      persists the choice to localStorage under the namespaced key
 *   3. After unmount + remount the persisted choice is honored on
 *      first render — initial render is in en
 *
 * Renders go through `renderWithRouter` so ThemeProvider is in place
 * (AuthShell mounts ThemeToggle which calls useTheme).
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthShell } from "./auth-shell";
import { i18n } from "../lib/i18n";
import { renderWithRouter } from "../test/fixtures/router";

const LS_KEY = "meeting-playbook.locale";

describe("LocaleToggle wired into AuthShell", () => {
  beforeEach(async () => {
    localStorage.removeItem(LS_KEY);
    await i18n.changeLanguage("zh-TW");
  });
  afterEach(async () => {
    cleanup();
    localStorage.removeItem(LS_KEY);
    await i18n.changeLanguage("zh-TW");
  });

  test("LocaleToggle trigger is reachable from AuthShell", async () => {
    await renderWithRouter(
      <AuthShell>
        <div data-testid="card-slot" />
      </AuthShell>,
      { initialEntries: ["/"], path: "/" },
    );
    expect(screen.getByTestId("locale-toggle")).toBeDefined();
  });

  test("clicking EN updates the visible subhead AND localStorage", async () => {
    const user = userEvent.setup();
    await renderWithRouter(
      <AuthShell>
        <div />
      </AuthShell>,
      { initialEntries: ["/"], path: "/" },
    );

    expect(screen.getByText("個人 AI 會議助理")).toBeDefined();

    await user.click(screen.getByTestId("locale-toggle"));
    const enOption = await screen.findByTestId("locale-option-en");
    await user.click(enOption);

    await waitFor(() => {
      expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
    });
    expect(localStorage.getItem(LS_KEY)).toBe("en");
  });

  test("after switch + cleanup + remount, the persisted locale is honored on first render", async () => {
    const user = userEvent.setup();
    const first = await renderWithRouter(
      <AuthShell>
        <div />
      </AuthShell>,
      { initialEntries: ["/"], path: "/" },
    );

    await user.click(screen.getByTestId("locale-toggle"));
    const enOption = await screen.findByTestId("locale-option-en");
    await user.click(enOption);
    await waitFor(() => expect(localStorage.getItem(LS_KEY)).toBe("en"));

    first.unmount();

    await renderWithRouter(
      <AuthShell>
        <div />
      </AuthShell>,
      { initialEntries: ["/"], path: "/" },
    );
    expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
  });
});
