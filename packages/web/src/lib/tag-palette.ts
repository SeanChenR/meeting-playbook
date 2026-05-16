/**
 * Tag palette — slice-17 task 1.2.
 *
 * Per design decision "Color palette: preset 8 色, 存 hex string, 前後端共用 enum":
 * one source of truth for the 8 tag colors lives here; the backend keeps a
 * parallel list in `packages/backend/meeting_playbook/tags/colors.py` and a
 * parity test (`tests/tags/test_palette_parity.py`) guarantees the two files
 * stay synchronized.
 *
 * Each color passes WCAG AA (≥ 4.5:1) against either `#1a1a1a` (dark text) or
 * `#ffffff` (light text). `pickReadableTextColor(bg)` returns the foreground
 * variant that pairs with the supplied background.
 */

export const TAG_PALETTE: readonly string[] = [
  // light-end backgrounds — use dark text on top
  "#DDD6FE",
  "#BFDBFE",
  "#A7F3D0",
  "#FEF3C7",
  "#FBCFE8",
  "#E5E7EB",
  // dark-end backgrounds — use light text on top
  "#7C2D12",
  "#1E3A8A",
] as const;

const LIGHT_FG_HEX = "#ffffff";
const DARK_FG_HEX = "#1a1a1a";

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

/**
 * Returns the text-color variant ("light" or "dark") that yields the better
 * contrast ratio against the supplied background. Light variant means a
 * near-white foreground; dark means near-black.
 */
export function pickReadableTextColor(background: string): "light" | "dark" {
  const lightContrast = _contrastRatio(background, LIGHT_FG_HEX);
  const darkContrast = _contrastRatio(background, DARK_FG_HEX);
  return darkContrast > lightContrast ? "dark" : "light";
}
