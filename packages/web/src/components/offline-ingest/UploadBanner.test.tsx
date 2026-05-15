/**
 * UploadBanner tests — slice-14 task 5.3.
 *
 * Per spec scenarios under
 * `Meeting detail conditional banner offers upload entry`:
 *   - past-end + scheduled + no recordings → banner present
 *   - end still in the future → banner hidden
 *   - recording already exists → banner hidden
 *
 * Bonus: the CTA button invokes the supplied `onUploadClick` callback so
 * the detail page can open its dialog.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { type MeetingDetail } from "@/lib/meetings-api";

import { UploadBanner } from "./UploadBanner";

afterEach(() => {
  cleanup();
});

function _meeting(overrides: Partial<MeetingDetail> = {}): MeetingDetail {
  return {
    id: "m_x",
    user_id: "u_x",
    title: "Banner test meeting",
    counterparty_display_name: "C",
    me_display_name: "M",
    status: "scheduled",
    asr_provider: "qwen3",
    calendar_event_id: null,
    created_at: "2026-05-10T09:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: "2026-05-10T09:00:00Z",
    scheduled_end_at: "2026-05-10T10:00:00Z",
    recordings_available: false,
    rerun_asr_pending: false,
    ...overrides,
  };
}

describe("UploadBanner", () => {
  test("renders the banner when end is past and no recordings exist", () => {
    const now = new Date("2026-05-10T12:00:00Z"); // 2 hours past scheduled_end_at
    render(<UploadBanner meeting={_meeting()} onUploadClick={() => undefined} now={now} />);

    expect(screen.getByTestId("offline-ingest-banner")).toBeDefined();
    expect(screen.getByRole("button", { name: /上傳音檔/ })).toBeDefined();
  });

  test("hides the banner when scheduled_end_at is still in the future", () => {
    const now = new Date("2026-05-10T09:30:00Z"); // 30 min BEFORE scheduled_end_at
    const { container } = render(
      <UploadBanner meeting={_meeting()} onUploadClick={() => undefined} now={now} />,
    );

    expect(container.querySelector("[data-testid='offline-ingest-banner']")).toBeNull();
  });

  test("hides the banner when the meeting already has a recording", () => {
    const now = new Date("2026-05-10T12:00:00Z");
    const { container } = render(
      <UploadBanner
        meeting={_meeting({ recordings_available: true })}
        onUploadClick={() => undefined}
        now={now}
      />,
    );

    expect(container.querySelector("[data-testid='offline-ingest-banner']")).toBeNull();
  });

  test("invokes onUploadClick when the CTA button is pressed", () => {
    const now = new Date("2026-05-10T12:00:00Z");
    const handler = mock(() => undefined);
    render(<UploadBanner meeting={_meeting()} onUploadClick={handler} now={now} />);

    fireEvent.click(screen.getByRole("button", { name: /上傳音檔/ }));
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
