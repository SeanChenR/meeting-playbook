/**
 * SpicyReveal tests — ui-overhaul-animated-surfaces task 6.6.
 *
 * Ported from uiverse `spicy-rat-83`. Plays once per `revealKey`; persists
 * the seen state under `localStorage["playbookRevealSeen:<key>"]`.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { SpicyReveal } from "./spicy-reveal";

beforeEach(() => {
  // @ts-expect-error happy-dom override
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
  window.localStorage.clear();
});

afterEach(cleanup);

describe("SpicyReveal", () => {
  test("first open plays the reveal (data-revealed=true after mount) and persists localStorage", () => {
    render(
      <SpicyReveal revealKey="m_42">
        <div data-testid="payload">Hello playbook</div>
      </SpicyReveal>,
    );
    expect(screen.getByTestId("payload")).toBeDefined();
    const wrap = screen.getByTestId("spicy-reveal");
    expect(wrap.getAttribute("data-played")).toBe("true");
    expect(window.localStorage.getItem("playbookRevealSeen:m_42")).not.toBeNull();
  });

  test("re-mount with persisted key skips the animation (data-played=skipped)", () => {
    window.localStorage.setItem("playbookRevealSeen:m_42", "1");
    render(
      <SpicyReveal revealKey="m_42">
        <div>x</div>
      </SpicyReveal>,
    );
    const wrap = screen.getByTestId("spicy-reveal");
    expect(wrap.getAttribute("data-played")).toBe("skipped");
  });

  test("reduced motion skips the animation but still persists seen flag", () => {
    // @ts-expect-error happy-dom override
    window.matchMedia = (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    render(
      <SpicyReveal revealKey="m_42">
        <div>x</div>
      </SpicyReveal>,
    );
    const wrap = screen.getByTestId("spicy-reveal");
    expect(wrap.getAttribute("data-reduced-motion")).toBe("true");
    expect(window.localStorage.getItem("playbookRevealSeen:m_42")).not.toBeNull();
  });
});
