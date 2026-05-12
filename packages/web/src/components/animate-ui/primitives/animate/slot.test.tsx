/**
 * Slot smoke — slice animate-ui-icons-swap task 1.3.
 *
 * Animate-UI's `Slot` primitive wraps a child element and merges its
 * own motion-aware props into the child, replacing scalar props (like
 * `data-testid`) and concatenating className via `cn`. Tests focus on
 * the structural contract:
 *   - renders the child's element type, not a new wrapper
 *   - threads className from both Slot + child onto the rendered node
 *
 * Deep motion semantics ship with the icon wrapper + per-icon tests.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { Slot } from "./slot";

afterEach(cleanup);

describe("Slot", () => {
  test("renders the child element type and merges className from both sides", () => {
    render(
      <Slot className="slot-className" data-testid="slot-host">
        <span className="child-className">hello</span>
      </Slot>,
    );
    const node = screen.getByTestId("slot-host");
    expect(node.tagName).toBe("SPAN");
    expect(node.className).toContain("slot-className");
    expect(node.className).toContain("child-className");
    expect(node.textContent).toBe("hello");
  });

  test("mounts an svg child without throwing (icon use case)", () => {
    expect(() =>
      render(
        <Slot data-testid="slot-svg">
          <svg viewBox="0 0 24 24">
            <path d="M0 0L24 24" />
          </svg>
        </Slot>,
      ),
    ).not.toThrow();
    const node = screen.getByTestId("slot-svg");
    expect(node.tagName.toLowerCase()).toBe("svg");
  });
});
