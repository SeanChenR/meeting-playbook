import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const signInSocial = mock(async () => ({ data: {} }));
const signInEmail = mock(async () => ({ data: { twoFactorRedirect: false }, error: null }));

mock.module("../lib/auth-client", () => ({
  authClient: {
    signIn: { social: signInSocial, email: signInEmail },
  },
}));

import { Login } from "./login";

describe("Login route", () => {
  beforeEach(() => {
    signInSocial.mockClear();
    signInEmail.mockClear();
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
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeDefined();
  });

  test("clicking the Google button dispatches signIn.social with google provider", async () => {
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

  test("renders email + password form fields", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText(/^email$/i)).toBeDefined();
    expect(screen.getByLabelText(/^password$/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeDefined();
  });

  test("submitting the email form dispatches signIn.email with credentials", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/^email$/i), "sean@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(signInEmail).toHaveBeenCalledTimes(1);
    const arg = signInEmail.mock.calls[0]?.[0] as { email: string; password: string };
    expect(arg.email).toBe("sean@example.com");
    expect(arg.password).toBe("hunter22hunter");
  });

  test("renders link to signup page", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    const signupLink = screen.getByRole("link", { name: /建立帳號/ });
    expect(signupLink.getAttribute("href")).toBe("/signup");
  });
});
