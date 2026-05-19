/**
 * GlassDock tests — ui-overhaul-animated-surfaces task 5.1.
 *
 * Generic Aura-token container: backdrop-blur + token-driven border /
 * radius (`--radius-lg`) / shadow. Does NOT position itself; callers
 * apply `className` for placement. Zero raw hex literals.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { GlassDock } from "./glass-dock";

afterEach(cleanup);

describe("GlassDock", () => {
  test("renders children", () => {
    render(
      <GlassDock>
        <span data-testid="child">hi</span>
      </GlassDock>,
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  test("applies backdrop-blur and rounded-lg utility classes", () => {
    render(<GlassDock>x</GlassDock>);
    const root = screen.getByTestId("glass-dock");
    expect(root.className).toContain("backdrop-blur");
    expect(root.className).toContain("rounded-lg");
  });

  test("forwards custom className", () => {
    render(<GlassDock className="fixed bottom-4">x</GlassDock>);
    const root = screen.getByTestId("glass-dock");
    expect(root.className).toContain("fixed");
    expect(root.className).toContain("bottom-4");
  });

  test("uses Aura tokens (no raw hex literals in className)", () => {
    render(<GlassDock>x</GlassDock>);
    const root = screen.getByTestId("glass-dock");
    expect(/#[0-9a-fA-F]{3,8}/.test(root.className)).toBe(false);
  });
});
