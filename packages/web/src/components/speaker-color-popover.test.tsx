/**
 * Tests for SpeakerColorPopover — slice-16 task 6.3.
 *
 * Five scenarios:
 *   (a) cluster=2 popover renders 5 scheme chips + 6 swatches + custom + reset
 *   (b) clicking a swatch persists an override for cluster 2
 *   (c) switching scheme rebuilds the swatch grid (testid changes)
 *   (d) reset removes overrides[2] but leaves overrides[1]
 *   (e) grayscale scheme renders achromatic swatches
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { SpeakerColorPopover } from "./speaker-color-popover";

const STORAGE_KEY = "meeting-playbook:transcript-color-pref";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function _Mount({ clusterN = 2 }: { clusterN?: number }) {
  const [open, setOpen] = useState(true);
  return <SpeakerColorPopover clusterN={clusterN} open={open} onOpenChange={setOpen} />;
}

describe("SpeakerColorPopover", () => {
  test("(a) renders 5 scheme chips + 6 swatches + reset (slice-16 task 10.2: no custom input)", () => {
    render(<_Mount />);
    expect(screen.getByTestId("scheme-chip-default")).toBeDefined();
    expect(screen.getByTestId("scheme-chip-vivid")).toBeDefined();
    expect(screen.getByTestId("scheme-chip-pastel")).toBeDefined();
    expect(screen.getByTestId("scheme-chip-high-contrast")).toBeDefined();
    expect(screen.getByTestId("scheme-chip-grayscale")).toBeDefined();
    expect(screen.getByTestId("color-swatch-1")).toBeDefined();
    expect(screen.getByTestId("color-swatch-6")).toBeDefined();
    expect(screen.queryByTestId("custom-color-input")).toBeNull();
    expect(screen.getByTestId("reset-override")).toBeDefined();
  });

  test("(b) clicking a swatch persists overrides[clusterN] as a hue number (slice-16 task 10.2)", async () => {
    const user = userEvent.setup();
    render(<_Mount clusterN={2} />);
    await user.click(screen.getByTestId("color-swatch-3"));
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    // Default scheme cluster 3 hue is 30 (third entry in [300, 150, 30, 240, 90, 0]).
    expect(stored.overrides["2"]).toBe(30);
    expect(typeof stored.overrides["2"]).toBe("number");
  });

  test("(c) switching scheme updates the swatch-grid testid suffix", async () => {
    const user = userEvent.setup();
    render(<_Mount />);
    expect(screen.getByTestId("swatch-grid-default")).toBeDefined();
    await user.click(screen.getByTestId("scheme-chip-vivid"));
    expect(screen.getByTestId("swatch-grid-vivid")).toBeDefined();
  });

  test("(d) reset removes overrides[2] but keeps overrides[1]", async () => {
    const user = userEvent.setup();
    // Pre-seed two hue-number overrides directly via the storage key.
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        scheme: "default",
        overrides: { 1: 180, 2: 240 },
      }),
    );
    render(<_Mount clusterN={2} />);
    await user.click(screen.getByTestId("reset-override"));
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.overrides["1"]).toBe(180);
    expect(stored.overrides["2"]).toBeUndefined();
  });

  test("(e) grayscale scheme hides the swatch grid and shows a hint (slice-16 task 10.2)", async () => {
    const user = userEvent.setup();
    render(<_Mount clusterN={2} />);
    await user.click(screen.getByTestId("scheme-chip-grayscale"));
    // Swatch grid is replaced by a hint section.
    expect(screen.queryByTestId("swatch-grid-grayscale")).toBeNull();
    expect(screen.getByTestId("swatch-grid-grayscale-hint")).toBeDefined();
    // Custom color input was removed from the popover entirely.
    expect(screen.queryByTestId("custom-color-input")).toBeNull();
  });
});
