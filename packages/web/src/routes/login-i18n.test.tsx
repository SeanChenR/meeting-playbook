/**
 * AC-3 i18n coverage for the Login route.
 *
 * Asserts that the same component renders different localized strings
 * based on i18n.language. Both languages share the same DOM structure;
 * only the user-visible text changes.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen } from "@testing-library/react";
import { i18n } from "../lib/i18n";
import { renderWithRouter } from "../test/fixtures/router";

mock.module("../lib/auth-client", () => ({
  authClient: {
    signIn: {
      social: async () => ({ data: {} }),
      email: async () => ({ data: { twoFactorRedirect: false }, error: null }),
    },
  },
}));

import { Login } from "./login";

describe("Login route — i18n", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });
  afterEach(async () => {
    cleanup();
    await i18n.changeLanguage("zh-TW");
  });

  test("renders zh-TW title and subtitle by default", async () => {
    await renderWithRouter(<Login />, { initialEntries: ["/login"], path: "/login" });
    expect(screen.getByText("歡迎回來")).toBeDefined();
    expect(screen.getByText("選擇登入方式以繼續")).toBeDefined();
    expect(screen.getByText("沒帳號？")).toBeDefined();
  });

  test("renders en title and subtitle after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    await renderWithRouter(<Login />, { initialEntries: ["/login"], path: "/login" });
    expect(screen.getByText("Welcome back")).toBeDefined();
    expect(screen.getByText("Choose a sign-in method to continue")).toBeDefined();
    expect(screen.getByText("No account?")).toBeDefined();
  });

  test("Sign in with Google button label is invariant across locales", async () => {
    await renderWithRouter(<Login />, { initialEntries: ["/login"], path: "/login" });
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeDefined();

    cleanup();
    await i18n.changeLanguage("en");
    await renderWithRouter(<Login />, { initialEntries: ["/login"], path: "/login" });
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeDefined();
  });
});
