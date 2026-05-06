import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const verifyTotpMock = mock(async () => ({ data: { verified: true } }));

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

  test("renders the 6-digit input and verify button", () => {
    render(
      <MemoryRouter>
        <TotpVerify />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText(/驗證碼/)).toBeDefined();
    expect(screen.getByRole("button", { name: /verify/i })).toBeDefined();
  });

  test("submitting the form dispatches verifyTotp with the entered code", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <TotpVerify />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/驗證碼/), "654321");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(verifyTotpMock).toHaveBeenCalledTimes(1);
    });
    const arg = verifyTotpMock.mock.calls[0]?.[0] as { code: string };
    expect(arg.code).toBe("654321");
  });
});
