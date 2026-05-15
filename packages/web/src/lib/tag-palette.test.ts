/**
 * Tag palette WCAG AA contrast verification (slice-17 task 1.2).
 *
 * The palette is shared between backend and frontend; the frontend exports
 * `pickReadableTextColor(bg) -> 'light' | 'dark'` so chip text colour can
 * be chosen deterministically.
 *
 * For each palette entry this test:
 *   - Computes the relative luminance (sRGB → linear → Y).
 *   - Picks the text-color tag (light foreground for dark bg, dark for
 *     light bg) via `pickReadableTextColor`.
 *   - Verifies the contrast ratio against the picked tag's reference
 *     foreground hex (`#ffffff` for "light", `#1a1a1a` for "dark") meets
 *     WCAG AA — 4.5:1 minimum.
 */

import { describe, expect, test } from "bun:test";
import { TAG_PALETTE, pickReadableTextColor } from "./tag-palette";

const LIGHT_FG = "#ffffff";
const DARK_FG = "#1a1a1a";

function _hexToRgb(hex: string): { r: number; g: number; b: number } {
  const m = hex.replace("#", "");
  return {
    r: parseInt(m.slice(0, 2), 16),
    g: parseInt(m.slice(2, 4), 16),
    b: parseInt(m.slice(4, 6), 16),
  };
}

function _relativeLuminance(hex: string): number {
  const { r, g, b } = _hexToRgb(hex);
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function _contrastRatio(a: string, b: string): number {
  const la = _relativeLuminance(a);
  const lb = _relativeLuminance(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

describe("tag-palette", () => {
  test("palette contains exactly 8 hex colors", () => {
    expect(TAG_PALETTE.length).toBe(8);
    for (const c of TAG_PALETTE) {
      expect(c).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  test("every palette color meets WCAG AA contrast against its chosen text color", () => {
    for (const bg of TAG_PALETTE) {
      const choice = pickReadableTextColor(bg);
      const fg = choice === "light" ? LIGHT_FG : DARK_FG;
      const ratio = _contrastRatio(bg, fg);
      expect(ratio).toBeGreaterThanOrEqual(4.5);
    }
  });

  test("pickReadableTextColor returns 'dark' for a light background", () => {
    expect(pickReadableTextColor("#FFFFFF")).toBe("dark");
  });

  test("pickReadableTextColor returns 'light' for a dark background", () => {
    expect(pickReadableTextColor("#000000")).toBe("light");
  });
});
