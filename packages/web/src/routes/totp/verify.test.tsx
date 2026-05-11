import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/fixtures/router";

const verifyTotpMock = mock(async (_arg: { code: string }) => ({ data: { verified: true } }));

mock.module("../../lib/auth-client", () => ({
  authClient: {
    twoFactor: {
      verifyTotp: verifyTotpMock,
    },
  },
}));

import { TotpVerify } from "./verify";

describe("TotpVerify route", () => {
  beforeEach(() => {
    verifyTotpMock.mockClear();
  });
  afterEach(() => {
    cleanup();
  });

  test("renders the 6-digit input and verify button", async () => {
    await renderWithRouter(<TotpVerify />, {
      initialEntries: ["/totp/verify"],
      path: "/totp/verify",
    });

    expect(screen.getByLabelText(/驗證碼/)).toBeDefined();
    expect(screen.getByRole("button", { name: /verify/i })).toBeDefined();
  });

  test("submitting the form dispatches verifyTotp with the entered code", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<TotpVerify />, {
      initialEntries: ["/totp/verify"],
      path: "/totp/verify",
    });

    await user.type(screen.getByLabelText(/驗證碼/), "654321");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(verifyTotpMock).toHaveBeenCalledTimes(1);
    });
    const arg = verifyTotpMock.mock.calls[0]?.[0] as unknown as { code: string };
    expect(arg.code).toBe("654321");
  });
});
