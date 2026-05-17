/**
 * ExportMeetingButton component tests (slice-22-export-bundle 4.3).
 *
 * Four scenarios per spec:
 *  - renders the localized button label ("匯出" / "Export").
 *  - disables and switches to spinner text during the fetch.
 *  - on HTTP 200 triggers a hidden `<a download>` click.
 *  - on 404 envelope surfaces a localized toast.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

import { ExportMeetingButton } from "./export-meeting-button";

// Capture toast() calls so we can assert error surfaces a localized message.
const toastCalls: { kind: "error" | "success"; message: string }[] = [];

mock.module("sonner", () => ({
  toast: Object.assign((message: string) => toastCalls.push({ kind: "success", message }), {
    error: (message: string) => toastCalls.push({ kind: "error", message }),
    success: (message: string) => toastCalls.push({ kind: "success", message }),
  }),
}));

const originalFetch = globalThis.fetch;
let fetchHandler: (url: string, init?: RequestInit) => Promise<Response>;

let originalCreateObjectURL: typeof URL.createObjectURL;
let originalRevokeObjectURL: typeof URL.revokeObjectURL;
let originalCreateElement: typeof document.createElement;
let clickedAnchors: HTMLAnchorElement[];

beforeEach(() => {
  toastCalls.length = 0;
  fetchHandler = async () =>
    new Response(new Blob([new Uint8Array([1])], { type: "application/zip" }), {
      status: 200,
      headers: {
        "content-type": "application/zip",
        "content-disposition": 'attachment; filename="meeting__2026-05-15.zip"',
      },
    });
  globalThis.fetch = mock((u: string, init?: RequestInit) =>
    fetchHandler(u, init),
  ) as unknown as typeof fetch;

  originalCreateObjectURL = URL.createObjectURL;
  originalRevokeObjectURL = URL.revokeObjectURL;
  originalCreateElement = document.createElement.bind(document);
  URL.createObjectURL = (() => "blob:mock") as typeof URL.createObjectURL;
  URL.revokeObjectURL = (() => undefined) as typeof URL.revokeObjectURL;
  clickedAnchors = [];
  document.createElement = ((tag: string) => {
    const el = originalCreateElement(tag);
    if (tag.toLowerCase() === "a") {
      const a = el as HTMLAnchorElement;
      a.click = () => {
        clickedAnchors.push(a);
      };
    }
    return el;
  }) as typeof document.createElement;
});

afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
  document.createElement = originalCreateElement;
});

function Harness({ children }: { children: ReactNode }) {
  return <div>{children}</div>;
}

describe("ExportMeetingButton", () => {
  test("renders the localized button label", () => {
    render(
      <Harness>
        <ExportMeetingButton meetingId="m_1" meetingTitle="Q3" scheduledStartAt={null} />
      </Harness>,
    );
    // i18n-test-setup defaults to zh-TW (project default).
    expect(screen.getByTestId("export-meeting-button").textContent).toContain("匯出");
  });

  test("disables and shows the in-flight label during fetch", async () => {
    let resolveFetch: ((r: Response) => void) | null = null;
    fetchHandler = () =>
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      });

    render(
      <Harness>
        <ExportMeetingButton meetingId="m_1" meetingTitle="Q3" scheduledStartAt={null} />
      </Harness>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByTestId("export-meeting-button"));

    await waitFor(() => {
      const btn = screen.getByTestId("export-meeting-button") as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
      expect(btn.textContent).toContain("匯出中");
    });

    // Resolve fetch with a success response to let cleanup run.
    resolveFetch?.(
      new Response(new Blob([new Uint8Array([1])], { type: "application/zip" }), {
        status: 200,
      }),
    );
  });

  test("triggers a hidden <a download> click on success", async () => {
    render(
      <Harness>
        <ExportMeetingButton meetingId="m_1" meetingTitle="Q3" scheduledStartAt={null} />
      </Harness>,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTestId("export-meeting-button"));

    await waitFor(() => {
      expect(clickedAnchors.length).toBe(1);
    });
  });

  test("shows a localized error toast on 404 envelope", async () => {
    fetchHandler = async () =>
      new Response(
        JSON.stringify({ error_code: "meeting.not_found", message: "Meeting not found" }),
        { status: 404, headers: { "content-type": "application/json" } },
      );

    render(
      <Harness>
        <ExportMeetingButton meetingId="m_x" meetingTitle="X" scheduledStartAt={null} />
      </Harness>,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTestId("export-meeting-button"));

    await waitFor(() => {
      expect(toastCalls.length).toBeGreaterThanOrEqual(1);
      // Either the mapped errors.meeting.not_found string, or the
      // exportFailed fallback prefix — both are localized via t().
      const last = toastCalls[toastCalls.length - 1];
      expect(last.kind).toBe("error");
      expect(typeof last.message).toBe("string");
      expect(last.message.length).toBeGreaterThan(0);
    });
    // Anchor click MUST NOT have been triggered on failure.
    expect(clickedAnchors.length).toBe(0);
  });
});
