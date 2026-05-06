/// <reference types="@testing-library/jest-dom" />
import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const signInSocial = mock(async () => ({ data: {} }));

mock.module("../lib/auth-client", () => ({
  authClient: {
    signIn: { social: signInSocial },
  },
}));

import { Login } from "./login";

describe("Login route", () => {
  beforeEach(() => {
    signInSocial.mockClear();
  });
  afterEach(() => {
    cleanup();
  });

  test("renders Sign in with Google button", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    const button = screen.getByRole("button", { name: /sign in with google/i });
    expect(button).toBeDefined();
  });

  test("clicking the button dispatches signIn.social with google provider", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /sign in with google/i }));

    expect(signInSocial).toHaveBeenCalledTimes(1);
    const arg = signInSocial.mock.calls[0]?.[0] as { provider: string; callbackURL: string };
    expect(arg.provider).toBe("google");
    expect(arg.callbackURL).toBe("/home");
  });
});
