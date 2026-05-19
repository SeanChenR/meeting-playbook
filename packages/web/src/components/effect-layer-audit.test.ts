/**
 * Effect-layer audit — ui-overhaul-animated-surfaces task 7.1 + 7.2.
 *
 * Enforces two cross-cutting requirements over the new effect-layer files:
 *
 *   1. Each file references the canonical reduced-motion source — either
 *      the shared `useReducedMotion` hook OR the Tailwind `motion-reduce`
 *      utility (which CSS-level resolves to the same media query).
 *
 *   2. Component className strings / inline style colour values consume
 *      Aura tokens via `--color-*` CSS variables only — zero raw hex
 *      literals and zero `rgb(`/`rgba(` function calls outside `index.css`.
 *
 * Runs in `bun:test` against the filesystem so violations surface in CI
 * without any browser instrumentation.
 */

import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;

const EFFECT_LAYER_FILES = [
  "components/animate-ui/backgrounds/stars.tsx",
  "components/magicui/animated-list.tsx",
  "components/ui/bar-visualizer.tsx",
  "components/ui/glass-dock.tsx",
  "components/ui/hover-glow-card.tsx",
  "components/ui/success-result.tsx",
  "components/ui/spicy-reveal.tsx",
] as const;

function _read(rel: string): string {
  return readFileSync(join(ROOT, rel), "utf8");
}

describe("effect-layer audit — reduced motion gate", () => {
  test.each(EFFECT_LAYER_FILES)(
    "%s references useReducedMotion or motion-reduce: utility",
    (path) => {
      const src = _read(path);
      const ok = src.includes("useReducedMotion") || src.includes("motion-reduce");
      expect(ok).toBe(true);
    },
  );
});

describe("effect-layer audit — Aura tokens only", () => {
  const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
  const RGB_RE = /\brgba?\s*\(/;

  test.each(EFFECT_LAYER_FILES)("%s has no raw hex literals", (path) => {
    const src = _read(path);
    expect(HEX_RE.test(src)).toBe(false);
  });

  test.each(EFFECT_LAYER_FILES)("%s has no rgb()/rgba() calls", (path) => {
    const src = _read(path);
    expect(RGB_RE.test(src)).toBe(false);
  });
});
