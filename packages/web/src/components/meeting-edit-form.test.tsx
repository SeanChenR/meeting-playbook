/**
 * MeetingEditForm tests — slice-15 task 4.1.
 *
 * Three scenarios:
 *   (a) Save title → PATCH dispatched, "Saved" flash shown, cache invalidated
 *   (b) end < start → form-level error, no PATCH
 *   (c) server 422 → localized error, Save button re-enabled
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { MeetingEditForm } from "./meeting-edit-form";
import { Dialog, DialogContent } from "./ui/dialog";
import { type MeetingDetail } from "@/lib/meetings-api";

afterEach(() => {
  cleanup();
  mock.restore();
});

function _withQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

// Slice-15 task 8.1: production usage wraps the form in a Dialog. The
// integration tests mount it the same way so we catch any Dialog-shape
// regressions (e.g. context provider missing, backdrop interception).
function _inDialog(children: ReactNode) {
  return (
    <Dialog open={true} onOpenChange={() => {}}>
      <DialogContent>{children}</DialogContent>
    </Dialog>
  );
}

function _meeting(): MeetingDetail {
  return {
    id: "m_edit",
    user_id: "u",
    title: "before",
    counterparty_display_name: "C",
    me_display_name: "M",
    status: "scheduled",
    asr_provider: "qwen3",
    calendar_event_id: null,
    created_at: "2026-05-01T00:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: "2026-06-15T14:00:00Z",
    scheduled_end_at: null,
    recordings_available: false,
    rerun_asr_pending: false,
  };
}

const _originalFetch = globalThis.fetch;

describe("MeetingEditForm", () => {
  test("saves a title edit → PATCH dispatched + Saved flash", async () => {
    let capturedUrl = "";
    let capturedInit: RequestInit | undefined;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedInit = init;
      const updated = { ..._meeting(), title: "after" };
      return new Response(JSON.stringify(updated), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const onSaved = mock(() => undefined);
    render(_withQueryClient(_inDialog(<MeetingEditForm meeting={_meeting()} onSaved={onSaved} />)));

    const titleInput = screen.getByLabelText(/標題/) as HTMLInputElement;
    fireEvent.change(titleInput, { target: { value: "after" } });
    fireEvent.click(screen.getByRole("button", { name: /儲存/ }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(capturedUrl).toBe("/api/meetings/m_edit");
    expect(capturedInit?.method).toBe("PATCH");
    expect(JSON.parse(String(capturedInit?.body))).toEqual({ title: "after" });

    expect(await screen.findByTestId("meeting-edit-saved-flash")).toBeDefined();

    globalThis.fetch = _originalFetch;
  });

  test("rejects end < start client-side (no PATCH dispatched)", async () => {
    let fetchCalled = 0;
    globalThis.fetch = (async () => {
      fetchCalled += 1;
      return new Response("{}", { status: 200 });
    }) as unknown as typeof fetch;

    render(
      _withQueryClient(
        _inDialog(<MeetingEditForm meeting={_meeting()} onSaved={() => undefined} />),
      ),
    );

    // Slice ui-overhaul-primitive-upgrade task 9: end field is now a
    // DateTimePicker composed of a date popover + time input. Open the
    // calendar popover and click the "today" link so end has a date that
    // happens to be before `meeting.scheduled_start_at` (2026-06-15);
    // any time-change after that will keep end < start.
    fireEvent.click(screen.getByTestId("meeting-edit-end-date") as HTMLElement);
    // The calendar's `today` button is rendered as a localized link;
    // grab by text via the i18n key fallback ("今天" in zh-TW / "Today" in en).
    const todayLink = await screen.findByText("今天");
    fireEvent.click(todayLink);
    fireEvent.change(screen.getByTestId("meeting-edit-end-time") as HTMLInputElement, {
      target: { value: "13:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: /儲存/ }));

    // Local-form validation must block the submission.
    await waitFor(() => expect(screen.queryByText(/結束時間必須晚於開始時間/)).not.toBeNull());
    expect(fetchCalled).toBe(0);

    globalThis.fetch = _originalFetch;
  });

  test("surfaces server 422 envelope + re-enables Save", async () => {
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          error_code: "meeting.invalid_time_range",
          message: "ignored — UI uses locale",
        }),
        { status: 422, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    render(
      _withQueryClient(
        _inDialog(<MeetingEditForm meeting={_meeting()} onSaved={() => undefined} />),
      ),
    );

    fireEvent.change(screen.getByLabelText(/標題/) as HTMLInputElement, {
      target: { value: "after" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /儲存/ }));
    });

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/結束時間必須晚於開始時間/);

    // Save button should be re-enabled (not disabled).
    const saveBtn = screen.getByRole("button", { name: /儲存/ }) as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(false);

    globalThis.fetch = _originalFetch;
  });
});
