/**
 * HoverGlowCard tests — ui-overhaul-animated-surfaces task 6.1.
 *
 * Ported from uiverse `cuddly-catfish-6`: subtle lift + border glow on
 * hover. Tokens only — no raw hex.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { HoverGlowCard } from "./hover-glow-card";

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

describe("HoverGlowCard", () => {
  test("renders children", () => {
    render(
      <HoverGlowCard>
        <span data-testid="child">x</span>
      </HoverGlowCard>,
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  test("applies hover transition utilities (lift + border glow)", () => {
    render(<HoverGlowCard>x</HoverGlowCard>);
    const root = screen.getByTestId("hover-glow-card");
    expect(root.className).toContain("transition");
    expect(root.className).toContain("hover:-translate-y-0.5");
    expect(root.className).toContain("hover:border-(--color-primary)");
  });

  test("no raw hex literals in className", () => {
    render(<HoverGlowCard>x</HoverGlowCard>);
    const root = screen.getByTestId("hover-glow-card");
    expect(/#[0-9a-fA-F]{3,8}/.test(root.className)).toBe(false);
  });

  test("under reduced motion, lift transition is suppressed via data-reduced-motion", () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(<HoverGlowCard>x</HoverGlowCard>);
    const root = screen.getByTestId("hover-glow-card");
    expect(root.getAttribute("data-reduced-motion")).toBe("true");
    expect(root.className).not.toContain("hover:-translate-y-0.5");
  });

  test("asChild merges classes onto the single child (preserves tagName + child data-testid)", () => {
    render(
      <HoverGlowCard asChild>
        <a href="/x" data-testid="anchor">
          link
        </a>
      </HoverGlowCard>,
    );
    const anchor = screen.getByTestId("anchor");
    expect(anchor.tagName).toBe("A");
    expect(anchor.className).toContain("hover:-translate-y-0.5");
    expect(anchor.getAttribute("data-hover-glow-card")).toBe("true");
  });
});
