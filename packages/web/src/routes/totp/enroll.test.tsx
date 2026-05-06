import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const enableMock = mock(async () => ({
  data: { totpURI: "otpauth://totp/MeetingPlaybook:sean?secret=ABC&issuer=MeetingPlaybook" },
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

  test("calls authClient.twoFactor.enable on mount", async () => {
    render(
      <MemoryRouter>
        <TotpEnroll />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(enableMock).toHaveBeenCalled();
    });
  });

  test("renders QR after enable resolves", async () => {
    render(
      <MemoryRouter>
        <TotpEnroll />
      </MemoryRouter>,
    );

    // happy-dom renders SVG as svg element; QRCodeSVG renders an <svg>.
    await waitFor(() => {
      const svg = document.querySelector("svg");
      expect(svg).not.toBeNull();
    });
  });

  test("submitting the form dispatches verifyTotp with the entered code", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <TotpEnroll />
      </MemoryRouter>,
    );

    const input = screen.getByLabelText(/輸入 6 位數驗證碼/);
    await user.type(input, "123456");

    const submit = screen.getByRole("button", { name: /verify/i });
    await user.click(submit);

    await waitFor(() => {
      expect(verifyTotpMock).toHaveBeenCalledTimes(1);
    });
    const arg = verifyTotpMock.mock.calls[0]?.[0] as { code: string };
    expect(arg.code).toBe("123456");
  });
});
