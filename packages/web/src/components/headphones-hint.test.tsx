/**
 * HeadphonesHint — refactor-meeting-detail-three-column tasks 8.1 / 11.2.
 *
 * Spec scenarios:
 *   - inline <Alert> (role="alert"), NOT Card
 *   - dismiss button is Lucide `X` icon, NOT × character
 *   - clicking dismiss unmounts the hint
 *   - full headphones-hint copy renders (no truncation)
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { HeadphonesHint } from "./headphones-hint";

afterEach(cleanup);

describe("HeadphonesHint", () => {
  test("renders the localized hint when visible=true", () => {
    render(<HeadphonesHint visible />);
    const el = screen.getByTestId("headphones-hint");
    expect(el).toBeDefined();
    expect(el.textContent).toContain("耳機");
  });

  test("returns null when visible=false (no DOM node)", () => {
    render(<HeadphonesHint visible={false} />);
    expect(screen.queryByTestId("headphones-hint")).toBeNull();
  });

  // ─── refactor-meeting-detail-three-column ────────────────────────────

  test("(8.1) alert element has role='alert' (shadcn-style, not Card)", () => {
    render(<HeadphonesHint visible />);
    const el = screen.getByTestId("headphones-hint");
    expect(el.getAttribute("role")).toBe("alert");
  });

  test("dismiss button renders Lucide X svg (Claude Design parity, no × char)", () => {
    render(<HeadphonesHint visible />);
    const btn = screen.getByTestId("headphones-hint-dismiss");
    expect(btn.querySelector("svg")).not.toBeNull();
    expect(btn.textContent ?? "").not.toContain("×");
  });

  test("clicking dismiss button unmounts the hint", () => {
    render(<HeadphonesHint visible />);
    expect(screen.getByTestId("headphones-hint")).toBeDefined();
    fireEvent.click(screen.getByTestId("headphones-hint-dismiss"));
    expect(screen.queryByTestId("headphones-hint")).toBeNull();
  });

  test("(11.2) full echo-risk copy renders, not truncated", () => {
    render(<HeadphonesHint visible />);
    const el = screen.getByTestId("headphones-hint");
    expect(el.textContent ?? "").toContain(
      "建議戴耳機避免回音 — 雙路 ASR 模式下，喇叭外放會被麥克風重複擷取。",
    );
    expect((el.textContent ?? "").endsWith("...")).toBe(false);
  });

  test("(9.5.1) no emoji glyphs in rendered alert", () => {
    render(<HeadphonesHint visible />);
    const el = screen.getByTestId("headphones-hint");
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    expect(emojiRegex.test(el.textContent ?? "")).toBe(false);
  });
});
