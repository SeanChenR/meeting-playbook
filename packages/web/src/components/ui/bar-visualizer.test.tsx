/**
 * BarVisualizer tests — ui-overhaul-animated-surfaces task 3.1.
 *
 * Reusable Aura-token bar visualizer independent of CaptureIndicator
 * domain knowledge. State × tone matrix + a11y assertions.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { BarVisualizer } from "./bar-visualizer";

beforeEach(() => {
  // @ts-expect-error happy-dom override
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(cleanup);

describe("BarVisualizer", () => {
  test("exposes role=img and aria-label", () => {
    render(<BarVisualizer state="listening" tone="me" ariaLabel="Microphone listening" />);
    const root = screen.getByRole("img", { name: "Microphone listening" });
    expect(root).toBeDefined();
  });

  test("renders default 10 bars when barCount omitted", () => {
    render(<BarVisualizer state="listening" tone="me" ariaLabel="x" />);
    const bars = screen.getAllByTestId("bar-visualizer-bar");
    expect(bars).toHaveLength(10);
  });

  test("honors custom barCount", () => {
    render(<BarVisualizer state="speaking" tone="them" barCount={6} ariaLabel="x" />);
    expect(screen.getAllByTestId("bar-visualizer-bar")).toHaveLength(6);
  });

  test.each([
    ["connecting", "warning", "var(--color-warning)"],
    ["listening", "me", "var(--color-me)"],
    ["speaking", "me", "var(--color-me)"],
    ["listening", "them", "var(--color-them)"],
    ["speaking", "them", "var(--color-them)"],
    ["connecting", "me", "var(--color-warning)"],
  ] as const)("state=%s tone=%s resolves color to %s", (state, tone, expected) => {
    render(<BarVisualizer state={state} tone={tone} ariaLabel="x" />);
    const bar = screen.getAllByTestId("bar-visualizer-bar")[0]!;
    expect(bar.style.background).toContain(expected);
  });

  test("state=off renders muted baseline with --color-border", () => {
    render(<BarVisualizer state="off" tone="me" ariaLabel="x" />);
    const bar = screen.getAllByTestId("bar-visualizer-bar")[0]!;
    expect(bar.style.background).toContain("var(--color-border)");
  });

  test("does not include raw hex literals in DOM", () => {
    render(<BarVisualizer state="speaking" tone="me" ariaLabel="x" />);
    const root = screen.getByRole("img");
    expect(/#[0-9a-fA-F]{3,8}/.test(root.outerHTML)).toBe(false);
  });

  test("reduced motion skips per-frame interpolation", () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(<BarVisualizer state="speaking" tone="me" ariaLabel="x" />);
    const root = screen.getByRole("img");
    expect(root.getAttribute("data-reduced-motion")).toBe("true");
  });
});
