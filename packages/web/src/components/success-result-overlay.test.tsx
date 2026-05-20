/**
 * SuccessResultOverlay — covers refactor task 16.1.
 *
 * Checks:
 *   (a) open=true renders backdrop + check icon + title + subtitle
 *   (b) open=false: nothing in DOM
 *   (c) autoDismissMs=300 calls onClose after timeout
 *   (d) ESC dismisses immediately
 *   (e) primary action click invokes onClick then onClose
 *   (f) no emoji glyphs in rendered DOM
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ThemeProvider } from "../lib/theme-provider";
import { SuccessResultOverlay } from "./success-result-overlay";

afterEach(cleanup);

function _renderOpen(props: Partial<Parameters<typeof SuccessResultOverlay>[0]> = {}) {
  const onClose = mock(() => {});
  const utils = render(
    <ThemeProvider initialTheme="light">
      <SuccessResultOverlay
        open
        title="音檔處理完成"
        subtitle="逐字稿已自動生成"
        autoDismissMs={0}
        onClose={onClose}
        {...props}
      />
    </ThemeProvider>,
  );
  return { ...utils, onClose };
}

describe("SuccessResultOverlay", () => {
  test("(a) open=true renders backdrop, check icon, title, subtitle", () => {
    _renderOpen();
    const overlay = screen.getByTestId("success-result-overlay");
    expect(overlay).toBeDefined();
    expect(overlay.className).toContain("backdrop-blur");
    expect(screen.getByText("音檔處理完成")).toBeDefined();
    expect(screen.getByText("逐字稿已自動生成")).toBeDefined();
    // CircleCheck Lucide icon renders as an <svg>
    expect(overlay.querySelector("svg")).not.toBeNull();
  });

  test("(b) open=false: not in DOM", () => {
    render(
      <ThemeProvider initialTheme="light">
        <SuccessResultOverlay open={false} title="x" onClose={() => {}} />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("success-result-overlay")).toBeNull();
  });

  test("(c) autoDismissMs=200 calls onClose after timeout", async () => {
    const { onClose } = _renderOpen({ autoDismissMs: 200 });
    expect(onClose).toHaveBeenCalledTimes(0);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 1000 });
  });

  test("(d) Escape key calls onClose", () => {
    const { onClose } = _renderOpen();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("(e) primary action click invokes both onClick and onClose", () => {
    const onAction = mock(() => {});
    const { onClose } = _renderOpen({
      primaryAction: { label: "查看逐字稿", onClick: onAction },
    });
    const btn = screen.getByRole("button", { name: "查看逐字稿" });
    fireEvent.click(btn);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("(f) no emoji glyphs in rendered overlay text", () => {
    _renderOpen();
    const overlay = screen.getByTestId("success-result-overlay");
    const text = overlay.textContent ?? "";
    // U+1F300-U+1FAFF (emoji), U+2600-U+27BF (misc symbols / dingbats)
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(text)).toBe(false);
  });
});
