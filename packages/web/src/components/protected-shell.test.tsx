/**
 * ProtectedShell — slice-07 fullBleed prop test.
 *
 * Mocks `authClient.useSession` so the shell renders without hitting the
 * Better Auth server.
 */

import { afterEach, beforeAll, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

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

  mock.module("@tanstack/react-router", () => ({
    Link: ({ children, ...props }: { children: React.ReactNode }) => <a {...props}>{children}</a>,
    useNavigate: () => () => undefined,
  }));
});

afterEach(cleanup);

const { ProtectedShell } = await import("./protected-shell");

describe("ProtectedShell.fullBleed", () => {
  test("default (no fullBleed) wraps children in centered max-width container", () => {
    render(
      <ProtectedShell>
        <div data-testid="child" />
      </ProtectedShell>,
    );
    const main = screen.getByTestId("protected-shell-main");
    expect(main.className).toContain("max-w-[1200px]");
    expect(main.className).toContain("mx-auto");
  });

  test("fullBleed=true removes the max-width container", () => {
    render(
      <ProtectedShell fullBleed>
        <div data-testid="child" />
      </ProtectedShell>,
    );
    const main = screen.getByTestId("protected-shell-main");
    expect(main.className).not.toContain("max-w-[1200px]");
    expect(main.className).not.toContain("mx-auto");
  });
});
