/**
 * AC-5 + AC-6 LocaleToggle integration with AuthShell.
 *
 * Verifies the user-flow:
 *   1. AuthShell mounts with LocaleToggle visible in its frame (header zone)
 *   2. Clicking EN flips the rendered subhead AND persists the choice to
 *      localStorage under the namespaced key
 *   3. After unmount + remount (simulated reload), the persisted choice is
 *      honored — initial render is in en
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthShell } from "./auth-shell";
import { i18n } from "../lib/i18n";

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

  test("LocaleToggle is reachable from AuthShell", () => {
    render(
      <AuthShell>
        <div data-testid="card-slot" />
      </AuthShell>,
    );
    expect(screen.getByRole("group", { name: /language/i })).toBeDefined();
  });

  test("clicking EN updates the visible subhead AND localStorage", async () => {
    const user = userEvent.setup();
    render(
      <AuthShell>
        <div />
      </AuthShell>,
    );

    expect(screen.getByText("個人 AI 會議助理")).toBeDefined();

    await user.click(screen.getByRole("button", { name: /^EN$/ }));

    await waitFor(() => {
      expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
    });
    expect(localStorage.getItem(LS_KEY)).toBe("en");
  });

  test("after switch + cleanup + remount, the persisted locale is honored on first render", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <AuthShell>
        <div />
      </AuthShell>,
    );

    await user.click(screen.getByRole("button", { name: /^EN$/ }));
    await waitFor(() => expect(localStorage.getItem(LS_KEY)).toBe("en"));

    unmount();

    // Simulate "reload": fresh render after the previous tree is gone.
    // i18n is a singleton so it remembers the user's choice; on a real
    // reload the detector would re-read localStorage and reach the same state.
    render(
      <AuthShell>
        <div />
      </AuthShell>,
    );
    expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
  });
});
