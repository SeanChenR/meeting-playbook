/**
 * Input tests — ui-overhaul-animated-surfaces task 6.4.
 *
 * Curvy variant (port of uiverse `curvy-earwig-22`) opts in via
 * `variant="curvy"`. Default variant DOM unchanged from baseline.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, render, screen } from "@testing-library/react";

import { Input } from "./input";

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

describe("Input", () => {
  test("default variant renders a single <input> with no label wrapper", () => {
    render(<Input data-testid="x" />);
    const root = screen.getByTestId("x");
    expect(root.tagName).toBe("INPUT");
    // No floating-label wrapper exposed.
    expect(screen.queryByTestId("curvy-label")).toBeNull();
  });

  test("default variant retains baseline className signature", () => {
    render(<Input data-testid="x" />);
    const root = screen.getByTestId("x");
    expect(root.className).toContain("border-(--color-input)");
    expect(root.className).toContain("rounded-md");
  });

  test("curvy variant wraps the input in a label-aware container", () => {
    render(<Input variant="curvy" label="Email" data-testid="x" />);
    expect(screen.getByTestId("curvy-wrap")).toBeDefined();
    expect(screen.getByTestId("curvy-label")).toBeDefined();
    expect(screen.getByText("Email")).toBeDefined();
  });

  test("curvy variant floats label on focus (data-focused=true)", () => {
    render(<Input variant="curvy" label="Email" data-testid="x" />);
    const input = screen.getByTestId("x") as HTMLInputElement;
    act(() => {
      input.focus();
      input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
    });
    const wrap = screen.getByTestId("curvy-wrap");
    expect(wrap.getAttribute("data-focused")).toBe("true");
  });

  test("curvy variant uses Aura tokens (no raw hex in className)", () => {
    render(<Input variant="curvy" label="Email" data-testid="x" />);
    const wrap = screen.getByTestId("curvy-wrap");
    expect(/#[0-9a-fA-F]{3,8}/.test(wrap.className)).toBe(false);
  });
});
