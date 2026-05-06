import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

let mockSessionData: {
  data: {
    user: {
      name: string | null;
      email: string;
      twoFactorEnabled?: boolean;
    };
  } | null;
  isPending: boolean;
} = {
  data: { user: { name: "Sean", email: "sean@example.com", twoFactorEnabled: false } },
  isPending: false,
};

const signOutMock = mock(async () => ({}));

mock.module("../lib/auth-client", () => ({
  authClient: {
    useSession: () => mockSessionData,
    signOut: signOutMock,
  },
}));

let fetchCalls: string[] = [];
const originalFetch = globalThis.fetch;

import { Home } from "./home";

describe("Home route", () => {
  beforeEach(() => {
    mockSessionData = {
      data: {
        user: { name: "Sean", email: "sean@example.com", twoFactorEnabled: false },
      },
      isPending: false,
    };
    fetchCalls = [];
    signOutMock.mockClear();
    globalThis.fetch = (async (input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input.toString();
      fetchCalls.push(url);
      if (url === "/api/me") {
        return new Response(JSON.stringify({ user_id: "usr_session_id" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("Not Found", { status: 404 });
    }) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders Hello, <name> when session is present", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Hello, Sean/)).toBeDefined();
  });

  test("renders backend confirmation after /api/me round-trip", async () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("backend-confirmation")).toBeDefined();
    });
    expect(screen.getByTestId("backend-confirmation").textContent).toContain("usr_session_id");
    expect(fetchCalls).toContain("/api/me");
  });

  test("falls back to email when name is null", () => {
    mockSessionData = {
      data: { user: { name: null, email: "fallback@example.com", twoFactorEnabled: false } },
      isPending: false,
    };

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Hello, fallback@example.com/)).toBeDefined();
  });

  test("shows loading state while session is pending", () => {
    mockSessionData = { data: null, isPending: true };

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByText(/loading/i)).toBeDefined();
  });

  test("renders Logout button and dispatches signOut on click", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    const button = screen.getByRole("button", { name: /logout/i });
    await user.click(button);
    expect(signOutMock).toHaveBeenCalledTimes(1);
  });

  test("renders Enable two-factor link when twoFactorEnabled is false", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const link = screen.getByTestId("enable-totp-link");
    expect(link.getAttribute("href")).toBe("/totp/enroll");
  });

  test("hides Enable link and shows status when twoFactorEnabled is true", () => {
    mockSessionData = {
      data: { user: { name: "Sean", email: "sean@example.com", twoFactorEnabled: true } },
      isPending: false,
    };

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("enable-totp-link")).toBeNull();
    expect(screen.getByTestId("totp-status").textContent).toContain("已啟用");
  });
});
