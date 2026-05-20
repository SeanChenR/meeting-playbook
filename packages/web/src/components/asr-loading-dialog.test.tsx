/**
 * AsrLoadingDialog — covers refactor task 12.1.
 *
 * Four spec scenarios:
 *   (a) phase="connecting" → dialog visible, contains BarVisualizer + title
 *   (b) phase="in_progress" → dialog absent
 *   (c) phase="error" → dialog absent
 *   (d) Escape keypress while connecting → dialog remains
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { i18n } from "../lib/i18n";
import { ThemeProvider } from "../lib/theme-provider";
import { AsrLoadingDialog, type AsrSessionPhase } from "./asr-loading-dialog";

afterEach(cleanup);

function _mount(phase: AsrSessionPhase) {
  return render(
    <ThemeProvider initialTheme="light">
      <I18nextProvider i18n={i18n}>
        <AsrLoadingDialog phase={phase} />
      </I18nextProvider>
    </ThemeProvider>,
  );
}

describe("AsrLoadingDialog", () => {
  test('(a) phase="connecting" → visible with BarVisualizer + title', () => {
    _mount("connecting");
    const dlg = screen.getByTestId("asr-loading-dialog");
    expect(dlg).toBeDefined();
    expect(screen.getByTestId("bar-visualizer")).toBeDefined();
    expect(dlg.textContent ?? "").toContain("正在啟動轉錄引擎");
  });

  test('(b) phase="in_progress" → dialog absent from DOM', () => {
    _mount("in_progress");
    expect(screen.queryByTestId("asr-loading-dialog")).toBeNull();
  });

  test('(c) phase="error" → dialog absent from DOM', () => {
    _mount("error");
    expect(screen.queryByTestId("asr-loading-dialog")).toBeNull();
  });

  test("(d) Escape keypress during connecting does not close (onOpenChange is no-op)", () => {
    _mount("connecting");
    expect(screen.getByTestId("asr-loading-dialog")).toBeDefined();
    fireEvent.keyDown(document, { key: "Escape" });
    // Dialog component swallows close request → still visible
    expect(screen.getByTestId("asr-loading-dialog")).toBeDefined();
  });

  test("(e) no emoji glyphs in rendered dialog text", () => {
    _mount("connecting");
    const dlg = screen.getByTestId("asr-loading-dialog");
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(dlg.textContent ?? "")).toBe(false);
  });
});
