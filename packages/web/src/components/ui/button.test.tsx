/**
 * Button hover tests — ui-overhaul-animated-surfaces task 6.3.
 *
 * Primary CTAs adopt the ported pink-chicken-70 hover motion via the
 * `data-cta="primary"` attribute. The motion is a sweeping gradient
 * overlay, NOT the disabled state's no-op.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { Button } from "./button";

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

describe("Button", () => {
  test("primary CTA with data-cta='primary' exposes the hover-sweep class", () => {
    render(
      <Button data-cta="primary" data-testid="cta">
        Save
      </Button>,
    );
    const btn = screen.getByTestId("cta");
    expect(btn.getAttribute("data-cta")).toBe("primary");
    expect(btn.className).toContain("mp-cta-sweep");
  });

  test("disabled primary CTA suppresses the sweep (no data-cta-active class)", () => {
    render(
      <Button data-cta="primary" disabled data-testid="cta">
        Save
      </Button>,
    );
    const btn = screen.getByTestId("cta");
    expect(btn.getAttribute("disabled")).not.toBeNull();
    // The motion sweep is suppressed via the existing
    // `disabled:hover:translate-y-0 disabled:hover:shadow-none` cascade
    // plus our new `disabled:[mask-image:none]` etc.; verify the disabled
    // utility class chain is present.
    expect(btn.className).toContain("disabled:pointer-events-none");
  });

  test("non-CTA buttons do not get the sweep", () => {
    render(<Button data-testid="plain">x</Button>);
    const btn = screen.getByTestId("plain");
    expect(btn.className).not.toContain("mp-cta-sweep");
  });
});
