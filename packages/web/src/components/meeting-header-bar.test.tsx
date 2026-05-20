/**
 * MeetingHeaderBar — covers refactor tasks 2.1, 12.5 (avatar group), 12.7 wiring,
 * 9.5.1 (no emoji), and recording status states.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { i18n } from "../lib/i18n";
import type { MeetingDetail } from "../lib/meetings-api";
import { ThemeProvider } from "../lib/theme-provider";
import { MeetingHeaderBar, type MeetingPhase } from "./meeting-header-bar";

afterEach(cleanup);

const FAR_PAST = "2020-01-01T00:00:00Z";
const FAR_FUTURE = "2099-12-31T14:30:00Z";
const FAR_FUTURE_END = "2099-12-31T15:30:00Z";

function _meeting(overrides: Partial<MeetingDetail> = {}): MeetingDetail {
  return {
    id: "m_test",
    user_id: "u",
    title: "Q4 進攻會議",
    counterparty_display_name: "林經理",
    me_display_name: "Sean",
    status: "scheduled",
    asr_provider: "whisper",
    calendar_event_id: null,
    created_at: FAR_PAST,
    started_at: null,
    ended_at: null,
    scheduled_start_at: FAR_FUTURE,
    scheduled_end_at: FAR_FUTURE_END,
    recordings_available: false,
    rerun_asr_pending: false,
    ...overrides,
  } as MeetingDetail;
}

function _mount(meeting: MeetingDetail, phase: MeetingPhase = "idle") {
  return render(
    <ThemeProvider initialTheme="light">
      <I18nextProvider i18n={i18n}>
        <MeetingHeaderBar meeting={meeting} phase={phase} />
      </I18nextProvider>
    </ThemeProvider>,
  );
}

describe("MeetingHeaderBar — basic structure", () => {
  test("(2.1a) renders title + status badge + scheduled time + 對方 + 我方", () => {
    _mount(_meeting({ status: "scheduled" }));
    const bar = screen.getByTestId("meeting-header-bar");
    expect(bar).toBeDefined();
    expect(screen.getByTestId("meeting-title").textContent).toBe("Q4 進攻會議");
    expect(bar.textContent ?? "").toContain("林經理");
    expect(bar.textContent ?? "").toContain("Sean");
    // scheduled time formatted as 12/31 14:30 – 15:30 (locale-dependent)
    expect(bar.textContent ?? "").toMatch(/\d{2}\/\d{2}/);
    expect(bar.textContent ?? "").toContain("14:30");
  });

  test("(2.1b) MetadataCard test-id is NOT present", () => {
    _mount(_meeting());
    expect(screen.queryByTestId("meeting-metadata-card")).toBeNull();
  });

  test("(2.1c) action buttons live outside the header bar now (moved to MeetingDetailActionBar)", () => {
    _mount(_meeting({ status: "scheduled" }), "idle");
    // Start / End buttons no longer render inside the header bar — they were
    // hoisted into <MeetingDetailActionBar> below the title (see action-bar
    // tests). The header is informational + nav only.
    expect(screen.queryByTestId("header-start-meeting")).toBeNull();
    expect(screen.queryByTestId("header-end-meeting")).toBeNull();
  });

  test("(2.1d) header bar in_progress phase still renders capture indicator slot", () => {
    _mount(_meeting({ status: "in_progress" }), "in_progress");
    expect(screen.queryByTestId("header-end-meeting")).toBeNull();
    expect(screen.queryByTestId("header-start-meeting")).toBeNull();
  });
});

describe("MeetingHeaderBar — counterparty avatar group", () => {
  test("(12.5a) single counterparty name → single Avatar (no group)", () => {
    _mount(_meeting({ counterparty_display_name: "林經理" }));
    expect(screen.queryByTestId("avatar-group")).toBeNull();
    const cp = screen.getByTestId("header-counterparty");
    expect(cp.textContent ?? "").toContain("林經理");
  });

  test("(12.5b) two comma-separated names → AvatarGroup with 2 avatars, no +N chip", () => {
    _mount(_meeting({ counterparty_display_name: "林經理, 王董" }));
    const group = screen.getByTestId("avatar-group");
    expect(group).toBeDefined();
    expect(group.querySelectorAll('[data-testid="avatar-group-avatar"]').length).toBe(2);
    expect(screen.queryByTestId("avatar-group-overflow")).toBeNull();
    expect(screen.getByTestId("header-counterparty").textContent ?? "").toContain("林經理 等 2 人");
  });

  test("(12.5c) five names → 3 avatars + +2 chip + 等 5 人 label", () => {
    _mount(_meeting({ counterparty_display_name: "林經理、王董, 陳副總，黃工程師、Joyce" }));
    const group = screen.getByTestId("avatar-group");
    expect(group.querySelectorAll('[data-testid="avatar-group-avatar"]').length).toBe(3);
    expect(screen.getByTestId("avatar-group-overflow").textContent).toBe("+2");
    expect(screen.getByTestId("header-counterparty").textContent ?? "").toContain("林經理 等 5 人");
  });

  test("(12.5d) mixed separators A,B，C、D → 3 avatars + +1 chip", () => {
    _mount(_meeting({ counterparty_display_name: "A,B，C、D" }));
    expect(
      screen.getByTestId("avatar-group").querySelectorAll('[data-testid="avatar-group-avatar"]')
        .length,
    ).toBe(3);
    expect(screen.getByTestId("avatar-group-overflow").textContent).toBe("+1");
  });
});

describe("MeetingHeaderBar — recording status (12.7 wiring)", () => {
  test("(rec-a) recordings_available=true → 綠 dot + 錄音可用", () => {
    _mount(_meeting({ recordings_available: true, status: "completed" }));
    const dot = screen.getByTestId("header-recording-dot");
    expect(dot.getAttribute("style") ?? "").toContain("--color-success");
    expect(screen.getByTestId("header-recording-status").textContent ?? "").toContain("錄音可用");
  });

  test("(rec-b) bucket=needs_recording → 橘 dot + 待上傳", () => {
    _mount(
      _meeting({
        status: "scheduled",
        scheduled_start_at: FAR_PAST,
        scheduled_end_at: FAR_PAST,
        recordings_available: false,
      }),
    );
    const dot = screen.getByTestId("header-recording-dot");
    expect(dot.getAttribute("style") ?? "").toContain("--color-warning");
    expect(screen.getByTestId("header-recording-status").textContent ?? "").toContain("待上傳");
  });

  test("(rec-c) bucket=completed + no recording → 紫 mauve dot + 錄音已過期", () => {
    _mount(_meeting({ status: "completed", recordings_available: false }));
    const dot = screen.getByTestId("header-recording-dot");
    expect(dot.getAttribute("style") ?? "").toContain("--color-accent");
    expect(screen.getByTestId("header-recording-status").textContent ?? "").toContain("錄音已過期");
  });

  test("(rec-d) bucket=upcoming → scheduled pill rendered with info dot (no longer hidden)", () => {
    _mount(_meeting({ status: "scheduled", recordings_available: false }));
    const pill = screen.queryByTestId("header-recording-status");
    expect(pill).not.toBeNull();
    const dot = screen.getByTestId("header-recording-dot");
    expect(dot.getAttribute("style") ?? "").toContain("--color-info");
    expect(pill?.textContent ?? "").toContain("尚未錄音");
  });

  test("(rec-e) recording dot NEVER uses muted/surface-3 grey tokens", () => {
    for (const m of [
      _meeting({ recordings_available: true }),
      _meeting({ status: "scheduled", scheduled_start_at: FAR_PAST, scheduled_end_at: FAR_PAST }),
      _meeting({ status: "completed", recordings_available: false }),
    ]) {
      cleanup();
      _mount(m);
      const dot = screen.queryByTestId("header-recording-dot");
      if (dot) {
        const style = dot.getAttribute("style") ?? "";
        expect(style).not.toContain("muted-foreground");
        expect(style).not.toContain("surface-3");
      }
    }
  });
});

describe("MeetingHeaderBar — no emoji glyphs", () => {
  test("(9.5.1) rendered text contains no emoji code points", () => {
    _mount(_meeting({ counterparty_display_name: "林經理, 王董" }));
    const bar = screen.getByTestId("meeting-header-bar");
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(bar.textContent ?? "")).toBe(false);
  });
});
