import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/fixtures/router";

const enableMock = mock(async () => ({
  data: {
    totpURI: "otpauth://totp/MeetingPlaybook:sean?secret=ABC&issuer=Meeting%20Playbook",
    backupCodes: ["aaaa-aaaa", "bbbb-bbbb", "cccc-cccc"],
  },
  error: null,
}));
const verifyTotpMock = mock(async () => ({ data: { verified: true } }));

mock.module("../../lib/auth-client", () => ({
  authClient: {
    twoFactor: {
      enable: enableMock,
      verifyTotp: verifyTotpMock,
    },
  },
}));

import { TotpEnroll } from "./enroll";

describe("TotpEnroll route", () => {
  beforeEach(() => {
    enableMock.mockClear();
    verifyTotpMock.mockClear();
  });
  afterEach(() => {
    cleanup();
  });

  test("step 1: renders password prompt before fetching QR", async () => {
    await renderWithRouter(<TotpEnroll />, {
      initialEntries: ["/totp/enroll"],
      path: "/totp/enroll",
    });
    expect(screen.getByLabelText(/^password$/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDefined();
    expect(enableMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("backup-codes")).toBeNull();
  });

  test("submitting password dispatches twoFactor.enable with the entered value", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<TotpEnroll />, {
      initialEntries: ["/totp/enroll"],
      path: "/totp/enroll",
    });

    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(enableMock).toHaveBeenCalledTimes(1);
    });
    const arg = enableMock.mock.calls[0]?.[0] as { password: string };
    expect(arg.password).toBe("hunter22hunter");
  });

  test("step 2: renders QR + backup codes after enable resolves", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<TotpEnroll />, {
      initialEntries: ["/totp/enroll"],
      path: "/totp/enroll",
    });

    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(document.querySelector("svg")).not.toBeNull();
      expect(screen.getByTestId("backup-codes")).toBeDefined();
    });

    const codes = screen.getByTestId("backup-codes").textContent ?? "";
    expect(codes).toContain("aaaa-aaaa");
    expect(codes).toContain("bbbb-bbbb");
    expect(codes).toContain("cccc-cccc");
  });

  test("step 3: submitting the 6-digit code dispatches verifyTotp", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<TotpEnroll />, {
      initialEntries: ["/totp/enroll"],
      path: "/totp/enroll",
    });

    await user.type(screen.getByLabelText(/^password$/i), "hunter22hunter");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/輸入 6 位數驗證碼/)).toBeDefined();
    });

    await user.type(screen.getByLabelText(/輸入 6 位數驗證碼/), "123456");
    await user.click(screen.getByRole("button", { name: /^verify$/i }));

    await waitFor(() => {
      expect(verifyTotpMock).toHaveBeenCalledTimes(1);
    });
    const arg = verifyTotpMock.mock.calls[0]?.[0] as { code: string };
    expect(arg.code).toBe("123456");
  });

  test("error from twoFactor.enable surfaces a localized error message", async () => {
    enableMock.mockImplementationOnce(async () => ({
      data: undefined as unknown as { totpURI: string; backupCodes: string[] },
      error: { message: "Invalid password" },
    }));

    const user = userEvent.setup();
    await renderWithRouter(<TotpEnroll />, {
      initialEntries: ["/totp/enroll"],
      path: "/totp/enroll",
    });

    await user.type(screen.getByLabelText(/^password$/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByTestId("totp-error").textContent).toContain("Invalid password");
    });
    expect(screen.queryByTestId("backup-codes")).toBeNull();
  });
});
