/**
 * AC-3 i18n coverage for the remaining auth routes (signup, totp.enroll,
 * totp.verify, home) and the shared AuthShell footer/subhead.
 *
 * Each describe block satisfies one Slice 2 task (3.2–3.6). The test pattern
 * is the same: render under zh-TW (default), assert localized text; switch
 * to en, re-render, assert switched text.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { AuthShell } from "../components/auth-shell";
import { i18n } from "../lib/i18n";

mock.module("../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: {
        user: {
          name: "Sean",
          email: "sean@example.com",
          image: null,
          twoFactorEnabled: false,
        },
      },
      isPending: false,
    }),
    signOut: async () => ({}),
    listAccounts: async () => ({ data: [{ providerId: "credential" }] }),
    signIn: {
      social: async () => ({ data: {} }),
      email: async () => ({ data: { twoFactorRedirect: false }, error: null }),
    },
    signUp: {
      email: async () => ({ data: { user: { id: "usr_new" } }, error: null }),
    },
    twoFactor: {
      enable: async () => ({
        data: { totpURI: "otpauth://test", backupCodes: ["aaa", "bbb"] },
        error: null,
      }),
      verifyTotp: async () => ({ data: {} }),
    },
    getSession: async () => ({ data: null }),
  },
}));

import { Home } from "./home";
import { Signup } from "./signup";
import { TotpEnroll } from "./totp/enroll";
import { TotpVerify } from "./totp/verify";

const wrap = (node: JSX.Element) => <MemoryRouter>{node}</MemoryRouter>;

beforeEach(async () => {
  await i18n.changeLanguage("zh-TW");
});
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("zh-TW");
});

// ─── Task 3.6: shared shell ─────────────────────────────────────────────
describe("AuthShell — i18n", () => {
  test("renders zh-TW subhead by default", () => {
    render(
      wrap(
        <AuthShell>
          <div />
        </AuthShell>,
      ),
    );
    expect(screen.getByText("個人 AI 會議助理")).toBeDefined();
  });

  test("renders en subhead after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    render(
      wrap(
        <AuthShell>
          <div />
        </AuthShell>,
      ),
    );
    expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
  });
});

// ─── Task 3.2: signup ────────────────────────────────────────────────────
describe("Signup — i18n", () => {
  test("renders zh-TW title by default", () => {
    render(wrap(<Signup />));
    expect(screen.getByText("建立 Email 帳號")).toBeDefined();
    expect(screen.getByText("已經有帳號？")).toBeDefined();
  });

  test("renders en title after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    render(wrap(<Signup />));
    expect(screen.getByText("Create email account")).toBeDefined();
    expect(screen.getByText("Already have an account?")).toBeDefined();
  });
});

// ─── Task 3.3: totp/enroll (step 1) ──────────────────────────────────────
describe("TotpEnroll — i18n", () => {
  test("renders zh-TW step-1 description by default", () => {
    render(wrap(<TotpEnroll />));
    expect(
      screen.getByText("請先確認密碼以開始 TOTP 註冊。Google-only 帳號需先連結密碼。"),
    ).toBeDefined();
  });

  test("renders en step-1 description after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    render(wrap(<TotpEnroll />));
    expect(screen.getByText(/Confirm your password to begin TOTP enrollment/i)).toBeDefined();
  });
});

// ─── Task 3.4: totp/verify ───────────────────────────────────────────────
describe("TotpVerify — i18n", () => {
  test("renders zh-TW title and description by default", () => {
    render(wrap(<TotpVerify />));
    expect(screen.getByText("輸入驗證碼")).toBeDefined();
    expect(screen.getByText("輸入 Authenticator 顯示的 6 位數驗證碼")).toBeDefined();
  });

  test("renders en title and description after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    render(wrap(<TotpVerify />));
    expect(screen.getByText("Enter verification code")).toBeDefined();
    expect(screen.getByText("Enter the 6-digit code from your authenticator app")).toBeDefined();
  });
});

// ─── Task 3.5: home greeting + interpolation ─────────────────────────────
describe("Home — i18n", () => {
  test("renders zh-TW greeting eyebrow + interpolated name", async () => {
    render(wrap(<Home />));
    await waitFor(() => expect(screen.getByText("已登入")).toBeDefined());
    expect(screen.getByText(/Hello, Sean/)).toBeDefined();
  });

  test("renders en greeting eyebrow after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    render(wrap(<Home />));
    await waitFor(() => expect(screen.getByText("Signed in")).toBeDefined());
    expect(screen.getByText(/Hello, Sean/)).toBeDefined();
  });
});
