/**
 * /settings/voice — slice-13 / ADR-0029 component tests.
 *
 * Verifies the four behavioural scenarios under spec requirement
 * "/settings/voice route lets the user record, preview, and save a
 * 30-second voice sample":
 *  (a) Pressing "開始錄製" shows the live level meter (recording started).
 *  (b) When recording stops, the preview audio element appears and the
 *      save button becomes enabled.
 *  (c) Save POSTs to /api/voice_enrollment and shows the localized
 *      "Saved" confirmation on HTTP 200.
 *  (d) On HTTP 422 voice_enrollment.invalid_sample, the localized error
 *      message appears AND the save button stays enabled for retry.
 *
 * MediaRecorder + getUserMedia are mocked so the test runs without a real
 * mic / browser audio stack. The auth-client mock mirrors the home route
 * test fixture so ProtectedShell does not redirect.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithRouter } from "../../test/fixtures/router";
import { SettingsVoice } from "./voice";

// ─── auth-client mock (same shape as home.test.tsx) ────────────────────

let mockSessionData: {
  data: {
    user: {
      name: string | null;
      email: string;
      image?: string | null;
      twoFactorEnabled?: boolean;
    };
  } | null;
  isPending: boolean;
} = {
  data: {
    user: { name: "Sean", email: "sean@example.com", image: null, twoFactorEnabled: true },
  },
  isPending: false,
};

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => mockSessionData,
    signOut: mock(async () => ({})),
    listAccounts: async () => ({ data: [{ providerId: "credential" }] }),
  },
}));

// `encodeWavFromBlob` hits Web Audio API (decodeAudioData + OfflineAudioContext)
// which happy-dom does not implement. The mock returns a synthetic WAV blob so
// the save-flow tests still exercise upload + status-handling, while leaving the
// real encoder verified by its own unit tests.
mock.module("../../lib/wav-encoder", () => ({
  encodeWavFromBlob: async (_input: Blob) =>
    new Blob([new Uint8Array(44 + 32)], { type: "audio/wav" }),
}));

// ─── MediaRecorder / AudioContext / getUserMedia mocks ─────────────────

interface FakeRecorder {
  state: "inactive" | "recording";
  ondataavailable: ((e: { data: Blob }) => void) | null;
  onstop: (() => void) | null;
  start(): void;
  stop(): void;
}

let lastRecorder: FakeRecorder | null = null;

class _MockMediaRecorder implements FakeRecorder {
  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor() {
    lastRecorder = this;
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    // Emit a single canned WAV chunk + fire onstop synchronously so the
    // component's blob state updates predictably for the test.
    this.ondataavailable?.({ data: new Blob([new Uint8Array(16)], { type: "audio/wav" }) });
    this.onstop?.();
  }
}

class _MockAnalyser {
  fftSize = 256;
  frequencyBinCount = 128;
  getByteTimeDomainData(buffer: Uint8Array) {
    buffer.fill(128); // silence → RMS 0
  }
}

class _MockAudioContext {
  createMediaStreamSource() {
    return { connect: () => {} };
  }
  createAnalyser() {
    return new _MockAnalyser();
  }
  async close() {
    /* no-op */
  }
}

const _stubStream = { getTracks: () => [{ stop: () => {} }] };

beforeEach(() => {
  // @ts-expect-error — overriding global for the test
  globalThis.MediaRecorder = _MockMediaRecorder;
  // @ts-expect-error — overriding global for the test
  globalThis.AudioContext = _MockAudioContext;
  // @ts-expect-error — partial nav.mediaDevices for the test
  globalThis.navigator.mediaDevices = {
    getUserMedia: async () => _stubStream,
  };
  // requestAnimationFrame stub for happy-dom (called by the level meter)
  globalThis.requestAnimationFrame = (() => 0) as typeof requestAnimationFrame;
  globalThis.cancelAnimationFrame = (() => {}) as typeof cancelAnimationFrame;
  // URL.createObjectURL stub — happy-dom does not implement it.
  globalThis.URL.createObjectURL = (() => "blob:fake") as typeof URL.createObjectURL;
  globalThis.URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
  lastRecorder = null;
});

afterEach(() => {
  cleanup();
});

// ─── fetch mock ────────────────────────────────────────────────────────

const originalFetch = globalThis.fetch;
let nextResponse: Response = new Response(JSON.stringify({ enrolled_at: "2026-05-15T01:00:00Z" }), {
  status: 200,
  headers: { "content-type": "application/json" },
});
let fetchCalls: { url: string; method: string }[] = [];

beforeEach(() => {
  fetchCalls = [];
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, method: init?.method ?? "GET" });
    if (url === "/api/me") {
      return new Response(JSON.stringify({ user_id: "usr_session_id" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url === "/api/voice_enrollment") {
      return nextResponse.clone();
    }
    return new Response("Not Found", { status: 404 });
  }) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

// ─── Tests ─────────────────────────────────────────────────────────────

describe("SettingsVoice route", () => {
  test("clicking 開始錄製 reveals the live level meter", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<SettingsVoice />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-start-button")).toBeDefined();
    });

    await user.click(screen.getByTestId("voice-start-button"));

    await waitFor(() => {
      expect(screen.getByTestId("voice-level-meter")).toBeDefined();
    });
  });

  test("stopping recording shows preview and enables save", async () => {
    const user = userEvent.setup();
    await renderWithRouter(<SettingsVoice />);

    await waitFor(() => screen.getByTestId("voice-start-button"));
    await user.click(screen.getByTestId("voice-start-button"));
    await waitFor(() => screen.getByTestId("voice-level-meter"));
    await user.click(screen.getByTestId("voice-stop-button"));

    await waitFor(() => {
      expect(screen.getByTestId("voice-preview")).toBeDefined();
    });
    const saveButton = screen.getByTestId("voice-save-button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(false);
  });

  test("save POSTs to /api/voice_enrollment and shows the saved confirmation", async () => {
    nextResponse = new Response(JSON.stringify({ enrolled_at: "2026-05-15T01:00:00Z" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const user = userEvent.setup();
    await renderWithRouter(<SettingsVoice />);

    await waitFor(() => screen.getByTestId("voice-start-button"));
    await user.click(screen.getByTestId("voice-start-button"));
    await waitFor(() => screen.getByTestId("voice-level-meter"));
    await user.click(screen.getByTestId("voice-stop-button"));
    await waitFor(() => screen.getByTestId("voice-save-button"));
    await user.click(screen.getByTestId("voice-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("voice-saved-confirmation")).toBeDefined();
    });
    const posted = fetchCalls.find((c) => c.url === "/api/voice_enrollment" && c.method === "POST");
    expect(posted).toBeDefined();
  });

  test("422 voice_enrollment.invalid_sample shows localized error; save stays enabled", async () => {
    nextResponse = new Response(
      JSON.stringify({
        error_code: "voice_enrollment.invalid_sample",
        message: "Pipeline detected 2 speakers in the sample",
      }),
      { status: 422, headers: { "content-type": "application/json" } },
    );
    const user = userEvent.setup();
    await renderWithRouter(<SettingsVoice />);

    await waitFor(() => screen.getByTestId("voice-start-button"));
    await user.click(screen.getByTestId("voice-start-button"));
    await waitFor(() => screen.getByTestId("voice-level-meter"));
    await user.click(screen.getByTestId("voice-stop-button"));
    await waitFor(() => screen.getByTestId("voice-save-button"));
    await user.click(screen.getByTestId("voice-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("voice-error")).toBeDefined();
    });
    // The displayed error message is the localized zh-TW string for the
    // voice_enrollment.invalid_sample key.
    expect(screen.getByTestId("voice-error").textContent).toContain("樣本驗證失敗");
    // Save button stays enabled so the user can retry.
    const saveButton = screen.getByTestId("voice-save-button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(false);
  });
});
