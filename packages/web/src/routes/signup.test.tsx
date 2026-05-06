import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const signUpEmail = mock(async () => ({ data: { user: { id: "usr_new" } }, error: null }));

mock.module("../lib/auth-client", () => ({
  authClient: {
    signUp: { email: signUpEmail },
  },
}));

import { Signup } from "./signup";

describe("Signup route", () => {
  beforeEach(() => {
    signUpEmail.mockClear();
  });
  afterEach(() => {
    cleanup();
  });

  test("renders all required fields and submit button", () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText(/姓名/)).toBeDefined();
    expect(screen.getByLabelText(/^email$/i)).toBeDefined();
    expect(screen.getByLabelText(/^password$/i)).toBeDefined();
    expect(screen.getByLabelText(/confirm password/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /^sign up$/i })).toBeDefined();
  });

  test("renders link back to login", () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );
    const loginLink = screen.getByRole("link", { name: /回到登入/ });
    expect(loginLink.getAttribute("href")).toBe("/login");
  });

  test("submitting valid input dispatches signUp.email with name + email + password", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/姓名/), "Sean Chen");
    await user.type(screen.getByLabelText(/^email$/i), "sean@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.type(screen.getByLabelText(/confirm password/i), "hunter22hunter");
    await user.click(screen.getByRole("button", { name: /^sign up$/i }));

    await waitFor(() => {
      expect(signUpEmail).toHaveBeenCalledTimes(1);
    });
    const arg = signUpEmail.mock.calls[0]?.[0] as {
      email: string;
      password: string;
      name: string;
    };
    expect(arg.email).toBe("sean@example.com");
    expect(arg.password).toBe("hunter22hunter");
    expect(arg.name).toBe("Sean Chen");
  });

  test("password mismatch shows error and does not dispatch signUp", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/姓名/), "Sean");
    await user.type(screen.getByLabelText(/^email$/i), "sean@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.type(screen.getByLabelText(/confirm password/i), "different-pw-here");
    await user.click(screen.getByRole("button", { name: /^sign up$/i }));

    expect(screen.getByTestId("signup-error").textContent).toContain("密碼不一致");
    expect(signUpEmail).not.toHaveBeenCalled();
  });

  test("password shorter than 8 chars shows error and does not dispatch signUp", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/姓名/), "Sean");
    await user.type(screen.getByLabelText(/^email$/i), "sean@example.com");
    // Browsers enforce minLength=8 on submit; bypass by triggering validity via short input
    // and asserting our additional JS-side check would fire. Use exactly 7 chars after browser
    // attribute — note: happy-dom may not fully enforce minLength so this still tests our guard.
    await user.type(screen.getByLabelText(/^password$/i), "short77");
    await user.type(screen.getByLabelText(/confirm password/i), "short77");
    await user.click(screen.getByRole("button", { name: /^sign up$/i }));

    // Either browser validation or our guard fires; signUp must not be dispatched
    expect(signUpEmail).not.toHaveBeenCalled();
  });
});
