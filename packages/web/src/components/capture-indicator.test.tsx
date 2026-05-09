/**
 * CaptureIndicator — visual state for active audio capture (slice-06).
 *
 * Three states: idle (no indicator), active (pulsing dot + label),
 * silence_warning (warning style + label).
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { CaptureIndicator } from "./capture-indicator";

afterEach(cleanup);

describe("CaptureIndicator", () => {
  test("idle state renders nothing visible (no indicator element)", () => {
    render(<CaptureIndicator state="idle" />);
    expect(screen.queryByTestId("capture-indicator")).toBeNull();
  });

  test("active state renders the indicator with capturing label", () => {
    render(<CaptureIndicator state="active" />);
    const el = screen.getByTestId("capture-indicator");
    expect(el.dataset.state).toBe("active");
    expect(el.textContent).toContain("擷取中");
  });

  test("silence_warning state renders the indicator with warning label", () => {
    render(<CaptureIndicator state="silence_warning" />);
    const el = screen.getByTestId("capture-indicator");
    expect(el.dataset.state).toBe("silence_warning");
    expect(el.textContent).toContain("未偵測到聲音");
  });
});
