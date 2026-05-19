/**
 * AnimatedList tests — ui-overhaul-animated-surfaces task 4.1.
 *
 * The pattern (extracted from magicui animated-list): each child mounts
 * with `opacity: 0 → 1` + `y: 8 → 0`. Reduced motion → no transition,
 * children render at final state.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { AnimatedList, AnimatedListItem } from "./animated-list";

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

describe("AnimatedList", () => {
  test("renders each child as a list item", () => {
    render(
      <AnimatedList as="ol">
        <AnimatedListItem>One</AnimatedListItem>
        <AnimatedListItem>Two</AnimatedListItem>
        <AnimatedListItem>Three</AnimatedListItem>
      </AnimatedList>,
    );
    const items = screen.getAllByTestId("animated-list-item");
    expect(items).toHaveLength(3);
  });

  test("exposes data-reduced-motion=false in motion-allowed mode", () => {
    render(
      <AnimatedList>
        <AnimatedListItem>x</AnimatedListItem>
      </AnimatedList>,
    );
    const item = screen.getByTestId("animated-list-item");
    expect(item.getAttribute("data-reduced-motion")).toBe("false");
  });

  test("exposes data-reduced-motion=true under reduced motion", () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(
      <AnimatedList>
        <AnimatedListItem>x</AnimatedListItem>
      </AnimatedList>,
    );
    const item = screen.getByTestId("animated-list-item");
    expect(item.getAttribute("data-reduced-motion")).toBe("true");
  });
});
