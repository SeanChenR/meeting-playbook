/**
 * NumberTicker smoke test — slice ui-overhaul-claude-design task 1.6.
 *
 * Asserts the component mounts and renders a numeric value. Spring-based
 * animations are hard to assert deterministically in happy-dom (no
 * requestAnimationFrame timing), so we just check the initial render lands
 * on a digit-shaped string and the `data-testid` is present.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { NumberTicker } from "./number-ticker";

afterEach(cleanup);

describe("NumberTicker", () => {
  test("renders the data-testid hook with a numeric content", () => {
    render(<NumberTicker value={5} />);
    const el = screen.getByTestId("number-ticker");
    expect(el).toBeDefined();
    // Initial render shows either the target value (5) or the from-zero
    // mid-spring value — both are digit-shaped.
    expect(el.textContent).toMatch(/^\d+(\.\d+)?$/);
  });

  test("updates value across re-renders without throwing", () => {
    const { rerender } = render(<NumberTicker value={0} />);
    expect(() => rerender(<NumberTicker value={42} />)).not.toThrow();
    expect(screen.getByTestId("number-ticker").textContent).toMatch(/^\d+(\.\d+)?$/);
  });
});
