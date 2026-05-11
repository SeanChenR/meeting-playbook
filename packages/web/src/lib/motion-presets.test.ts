/**
 * motion-presets shape tests — slice ui-overhaul-claude-design task 1.5.
 *
 * Confirms each exported preset has the framer-motion shape components
 * expect (`initial` + `animate` for Variants, callable for Transition).
 * Ensures rename-detection: removing or renaming a preset breaks this file
 * before it breaks downstream components.
 */

import { describe, expect, test } from "bun:test";

import { cardHover, modalScale, paneEnter, paneStagger, tabContent } from "./motion-presets";

describe("motion-presets", () => {
  test("paneEnter has initial + animate states", () => {
    expect(paneEnter.initial).toBeDefined();
    expect(paneEnter.animate).toBeDefined();
  });

  test("paneStagger declares staggerChildren", () => {
    expect((paneStagger as { staggerChildren?: number }).staggerChildren).toBeGreaterThan(0);
  });

  test("tabContent has initial + animate + exit states", () => {
    expect(tabContent.initial).toBeDefined();
    expect(tabContent.animate).toBeDefined();
    expect(tabContent.exit).toBeDefined();
  });

  test("modalScale has scale-down initial state", () => {
    expect((modalScale.initial as { scale?: number }).scale).toBeLessThan(1);
  });

  test("cardHover declares rest + hover variants", () => {
    expect(cardHover.rest).toBeDefined();
    expect(cardHover.hover).toBeDefined();
  });
});
