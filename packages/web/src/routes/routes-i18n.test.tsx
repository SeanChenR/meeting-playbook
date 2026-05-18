/**
 * AC-3 i18n coverage for the remaining auth routes (signup, totp.enroll,
 * totp.verify, home) and the shared AuthShell footer/subhead.
 *
 * Each describe block satisfies one Slice 2 task (3.2–3.6). The test pattern
 * is the same: render under zh-TW (default), assert localized text; switch
 * to en, re-render, assert switched text.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { AuthShell } from "../components/auth-shell";
import { i18n } from "../lib/i18n";
import { renderWithRouter } from "../test/fixtures/router";

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

// Slice-18: legacy Home route removed; greeting/eyebrow strings retired.
import { Signup } from "./signup";
import { TotpEnroll } from "./totp/enroll";
import { TotpVerify } from "./totp/verify";

async function wrap(node: ReactElement, path = "/") {
  // Phase 6 cleanup: every shell (AuthShell + ProtectedShell) now consumes
  // ThemeContext via ThemeToggle, so always go through `renderWithRouter`
  // which wraps in ThemeProvider for us. Even though AuthShell doesn't need
  // a router, the fixture is harmless here.
  return renderWithRouter(node, { initialEntries: [path], path });
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-TW");
});
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("zh-TW");
});

// ─── Task 3.6: shared shell ─────────────────────────────────────────────
describe("AuthShell — i18n", () => {
  test("renders zh-TW subhead by default", async () => {
    await wrap(
      <AuthShell>
        <div />
      </AuthShell>,
    );
    expect(screen.getByText("個人 AI 會議助理")).toBeDefined();
  });

  test("renders en subhead after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    await wrap(
      <AuthShell>
        <div />
      </AuthShell>,
    );
    expect(screen.getByText("Personal AI meeting assistant")).toBeDefined();
  });
});

// ─── Task 3.2: signup ────────────────────────────────────────────────────
describe("Signup — i18n", () => {
  test("renders zh-TW title by default", async () => {
    await wrap(<Signup />);
    expect(screen.getByText("建立 Email 帳號")).toBeDefined();
    expect(screen.getByText("已經有帳號？")).toBeDefined();
  });

  test("renders en title after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    await wrap(<Signup />);
    expect(screen.getByText("Create email account")).toBeDefined();
    expect(screen.getByText("Already have an account?")).toBeDefined();
  });
});

// ─── Task 3.3: totp/enroll (step 1) ──────────────────────────────────────
describe("TotpEnroll — i18n", () => {
  test("renders zh-TW step-1 description by default", async () => {
    await wrap(<TotpEnroll />);
    expect(
      screen.getByText("請先確認密碼以開始 TOTP 註冊。Google-only 帳號需先連結密碼。"),
    ).toBeDefined();
  });

  test("renders en step-1 description after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    await wrap(<TotpEnroll />);
    expect(screen.getByText(/Confirm your password to begin TOTP enrollment/i)).toBeDefined();
  });
});

// ─── Task 3.4: totp/verify ───────────────────────────────────────────────
describe("TotpVerify — i18n", () => {
  test("renders zh-TW title and description by default", async () => {
    await wrap(<TotpVerify />);
    expect(screen.getByText("輸入驗證碼")).toBeDefined();
    expect(screen.getByText("輸入 Authenticator 顯示的 6 位數驗證碼")).toBeDefined();
  });

  test("renders en title and description after changeLanguage('en')", async () => {
    await i18n.changeLanguage("en");
    await wrap(<TotpVerify />);
    expect(screen.getByText("Enter verification code")).toBeDefined();
    expect(screen.getByText("Enter the 6-digit code from your authenticator app")).toBeDefined();
  });
});

// Slice-18: Home — i18n describe block removed with legacy Home component.

// ─── P4 IA refactor: /recordings page locale parity ───────────────────
//
// Drops legacy `/calendar/import` route assertions (the route no longer
// exists) and asserts the new `/recordings` page renders its zh-TW + en
// headings via the `recordings.list.heading` namespace.
//
// Uses a fetch stub instead of `mock.module("../lib/recordings-api")` so
// the global recordings-api module stays intact for sibling tests in the
// same `bun test` run (mock.module is process-global with no teardown).

import { i18n as i18nForRecordings } from "../lib/i18n";
import { RecordingsIndex } from "./recordings";

describe("/recordings — i18n", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.startsWith("/api/recordings")) {
        return new Response(JSON.stringify({ recordings: [], total: 0, page: 1, page_size: 25 }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("renders zh-TW heading by default", async () => {
    await i18nForRecordings.changeLanguage("zh-TW");
    await wrap(<RecordingsIndex />, "/recordings");
    expect(screen.getAllByText("錄音檔").length).toBeGreaterThan(0);
    expect(screen.getByText("保留 30 天內的所有錄音檔")).toBeDefined();
  });

  test("renders en heading after changeLanguage('en')", async () => {
    await i18nForRecordings.changeLanguage("en");
    await wrap(<RecordingsIndex />, "/recordings");
    expect(screen.getAllByText("Recordings").length).toBeGreaterThan(0);
    expect(screen.getByText("All recordings within the 30-day Recording window")).toBeDefined();
  });
});
