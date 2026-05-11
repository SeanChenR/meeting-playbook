/**
 * RecordingBadge — slice-11 task 6.1 component test.
 *
 * Per spec meeting-detail-layout scenarios:
 *   - available=true  → data-state="available" + 「錄音可用」/ "Recording available"
 *   - available=false → data-state="expired"   + 「錄音已過期」/ "Recording expired"
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { RecordingBadge } from "./recording-badge";

afterEach(cleanup);

describe("RecordingBadge", () => {
  test("available=true renders state=available + zh-TW '錄音可用'", () => {
    render(<RecordingBadge available />);
    const badge = screen.getByTestId("recording-badge");
    expect(badge.getAttribute("data-state")).toBe("available");
    expect(badge.textContent).toContain("錄音可用");
  });

  test("available=false renders state=expired + zh-TW '錄音已過期'", () => {
    render(<RecordingBadge available={false} />);
    const badge = screen.getByTestId("recording-badge");
    expect(badge.getAttribute("data-state")).toBe("expired");
    expect(badge.textContent).toContain("錄音已過期");
  });
});
