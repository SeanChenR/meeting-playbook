/**
 * MeetingOverflowMenu — covers refactor tasks 3.1, 14.1, 11.3 (sub-hint), 9.5.1 (no emoji).
 *
 * 8 items (ASR removed by Decision 12):
 *   edit / tags / attachments / linked / separator / mode (cond) / rerun / separator / delete
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { i18n } from "../lib/i18n";
import { ThemeProvider } from "../lib/theme-provider";
import { MeetingOverflowMenu } from "./meeting-overflow-menu";

afterEach(cleanup);

interface Callbacks {
  onEdit: ReturnType<typeof mock>;
  onTagsOpen: ReturnType<typeof mock>;
  onAttachmentsOpen: ReturnType<typeof mock>;
  onLinkedOpen: ReturnType<typeof mock>;
  onAsrOpen: ReturnType<typeof mock>;
  onModeOpen: ReturnType<typeof mock>;
  onRerun: ReturnType<typeof mock>;
  onDelete: ReturnType<typeof mock>;
}

function _mount(
  overrides: Partial<{
    attachmentsCount: number;
    linksCount: number;
    asrCurrentLabel?: string;
    modeCurrentLabel?: string;
    showModeItem: boolean;
  }> = {},
): Callbacks {
  const callbacks: Callbacks = {
    onEdit: mock(() => {}),
    onTagsOpen: mock(() => {}),
    onAttachmentsOpen: mock(() => {}),
    onLinkedOpen: mock(() => {}),
    onAsrOpen: mock(() => {}),
    onModeOpen: mock(() => {}),
    onRerun: mock(() => {}),
    onDelete: mock(() => {}),
  };
  render(
    <ThemeProvider initialTheme="light">
      <I18nextProvider i18n={i18n}>
        <MeetingOverflowMenu
          attachmentsCount={overrides.attachmentsCount ?? 3}
          linksCount={overrides.linksCount ?? 2}
          asrCurrentLabel={overrides.asrCurrentLabel}
          modeCurrentLabel={overrides.modeCurrentLabel}
          showModeItem={overrides.showModeItem ?? true}
          {...callbacks}
        />
      </I18nextProvider>
    </ThemeProvider>,
  );
  return callbacks;
}

async function _openMenu() {
  const user = userEvent.setup();
  await user.click(screen.getByTestId("meeting-overflow-trigger"));
  await waitFor(() => {
    expect(screen.queryByTestId("meeting-menu-item-edit")).not.toBeNull();
  });
  return user;
}

describe("MeetingOverflowMenu — 9-item structure (Claude Design v2: ASR included)", () => {
  test("(3.1a) menu opens with all expected items including ASR", async () => {
    _mount({
      attachmentsCount: 3,
      linksCount: 2,
      showModeItem: true,
      asrCurrentLabel: "Whisper Large v3",
    });
    await _openMenu();
    expect(screen.queryByTestId("meeting-menu-item-edit")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-tags")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-attachments")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-linked")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-asr")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-mode")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-rerun")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-delete")).not.toBeNull();
  });

  test("(3.1b) attachments / linked items show count badges", async () => {
    _mount({ attachmentsCount: 3, linksCount: 2 });
    await _openMenu();
    expect(screen.getByTestId("meeting-menu-item-attachments").textContent ?? "").toContain("3");
    expect(screen.getByTestId("meeting-menu-item-linked").textContent ?? "").toContain("2");
  });

  test("(3.1c) delete item has destructive styling", async () => {
    _mount();
    await _openMenu();
    const del = screen.getByTestId("meeting-menu-item-delete");
    expect(del.className).toContain("destructive");
  });

  test("(3.1d) showModeItem=false → mode item NOT in DOM", async () => {
    _mount({ showModeItem: false });
    await _openMenu();
    expect(screen.queryByTestId("meeting-menu-item-mode")).toBeNull();
    // Other items still present
    expect(screen.queryByTestId("meeting-menu-item-edit")).not.toBeNull();
    expect(screen.queryByTestId("meeting-menu-item-rerun")).not.toBeNull();
  });
});

describe("MeetingOverflowMenu — sub-hints for ASR and Mode (Claude Design v2)", () => {
  test("(11.3a) modeCurrentLabel='雙路 ASR' renders sub-hint", async () => {
    _mount({ modeCurrentLabel: "雙路 ASR", showModeItem: true });
    await _openMenu();
    expect(screen.getByTestId("meeting-menu-item-mode").textContent ?? "").toContain("雙路 ASR");
  });

  test("(11.3b) asrCurrentLabel='Whisper Large v3' renders sub-hint", async () => {
    _mount({ asrCurrentLabel: "Whisper Large v3" });
    await _openMenu();
    expect(screen.getByTestId("meeting-menu-item-asr").textContent ?? "").toContain(
      "Whisper Large v3",
    );
  });

  test("(11.3c) sub-hints absent when labels undefined", async () => {
    _mount({ asrCurrentLabel: undefined, modeCurrentLabel: undefined, showModeItem: true });
    await _openMenu();
    const asr = screen.getByTestId("meeting-menu-item-asr");
    const mode = screen.getByTestId("meeting-menu-item-mode");
    expect(asr.textContent ?? "").not.toMatch(/Whisper|Qwen|Cloud/);
    expect(mode.textContent ?? "").not.toMatch(/雙路|Dual ASR|單路|Single/);
  });
});

describe("MeetingOverflowMenu — callbacks fire on item click", () => {
  test("(cb-edit) click edit → onEdit fires once", async () => {
    const cbs = _mount();
    const user = await _openMenu();
    await user.click(screen.getByTestId("meeting-menu-item-edit"));
    expect(cbs.onEdit).toHaveBeenCalledTimes(1);
  });

  test("(cb-delete) click delete → onDelete fires once", async () => {
    const cbs = _mount();
    const user = await _openMenu();
    await user.click(screen.getByTestId("meeting-menu-item-delete"));
    expect(cbs.onDelete).toHaveBeenCalledTimes(1);
  });

  test("(cb-attachments) click attachments → onAttachmentsOpen fires once", async () => {
    const cbs = _mount();
    const user = await _openMenu();
    await user.click(screen.getByTestId("meeting-menu-item-attachments"));
    expect(cbs.onAttachmentsOpen).toHaveBeenCalledTimes(1);
  });
});

describe("MeetingOverflowMenu — no emoji glyphs", () => {
  test("(9.5.1) trigger + open menu contain no emoji code points", async () => {
    _mount();
    const trigger = screen.getByTestId("meeting-overflow-trigger");
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(trigger.textContent ?? "")).toBe(false);
    await _openMenu();
    const items = [
      "meeting-menu-item-edit",
      "meeting-menu-item-tags",
      "meeting-menu-item-attachments",
      "meeting-menu-item-linked",
      "meeting-menu-item-mode",
      "meeting-menu-item-rerun",
      "meeting-menu-item-delete",
    ];
    for (const id of items) {
      const el = screen.queryByTestId(id);
      if (el) expect(emojiRegex.test(el.textContent ?? "")).toBe(false);
    }
  });
});
