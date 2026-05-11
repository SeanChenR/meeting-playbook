/**
 * ProtectedShell tests — slice ui-overhaul-claude-design task 2.1.
 *
 * Covers:
 *   - fullBleed prop (slice-07 baseline behaviour)
 *   - NavBar height 56px + sticky top
 *   - Right-side cluster contains locale-toggle / theme-toggle / avatar / logout
 *
 * Uses the shared `renderWithRouter` fixture so we don't have to mock
 * `@tanstack/react-router` — Bun's `mock.module` is process-global and
 * mocking the router globally leaks into route tests that need real
 * navigation (e.g. delete-confirm flows). The fixture already wraps in
 * ThemeProvider so ThemeToggle works.
 *
 * Only `auth-client` is mocked, scoped to a session that always resolves,
 * so the shell doesn't redirect to /login during render.
 */

import { afterEach, beforeAll, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen } from "@testing-library/react";

beforeAll(() => {
  mock.module("../lib/auth-client", () => ({
    authClient: {
      useSession: () => ({
        data: { user: { id: "u_1", name: "Sean", email: "sean@example.com" } },
        isPending: false,
      }),
      signOut: async () => undefined,
    },
  }));
});

beforeEach(() => {
  // happy-dom needs matchMedia stub so ThemeProvider initialises cleanly
  // when rendered through the fixture.
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

const { ProtectedShell } = await import("./protected-shell");
const { renderWithRouter } = await import("../test/fixtures/router");

describe("ProtectedShell layout", () => {
  test("default wraps children in 1600px centred main", async () => {
    await renderWithRouter(
      <ProtectedShell>
        <div data-testid="child" />
      </ProtectedShell>,
      { initialEntries: ["/x"], path: "/x" },
    );
    const main = screen.getByTestId("protected-shell-main");
    expect(main.className).toContain("max-w-[1600px]");
    expect(main.className).toContain("mx-auto");
  });

  test("fullBleed removes the max-width container", async () => {
    await renderWithRouter(
      <ProtectedShell fullBleed>
        <div data-testid="child" />
      </ProtectedShell>,
      { initialEntries: ["/x"], path: "/x" },
    );
    const main = screen.getByTestId("protected-shell-main");
    expect(main.className).not.toContain("max-w-[1600px]");
    expect(main.className).not.toContain("mx-auto");
  });
});

describe("ProtectedShell NavBar", () => {
  test("renders a sticky 56px navbar (h-14 sticky)", async () => {
    await renderWithRouter(
      <ProtectedShell>
        <div />
      </ProtectedShell>,
      { initialEntries: ["/x"], path: "/x" },
    );
    const navbar = screen.getByTestId("navbar");
    expect(navbar.className).toContain("h-14");
    expect(navbar.className).toContain("sticky");
    expect(navbar.className).toContain("top-0");
  });

  test("right-cluster contains theme-toggle, avatar, and logout-button", async () => {
    await renderWithRouter(
      <ProtectedShell>
        <div />
      </ProtectedShell>,
      { initialEntries: ["/x"], path: "/x" },
    );
    expect(screen.getByTestId("theme-toggle")).toBeDefined();
    expect(screen.getByTestId("user-avatar")).toBeDefined();
    expect(screen.getByTestId("logout-button")).toBeDefined();
  });
});
