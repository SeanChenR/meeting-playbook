/**
 * Transcript cluster color schemes — slice-16 task 6.1.
 *
 * Five hard-coded palettes the user can pick from for transcript
 * speaker_cluster_<N> rendering, plus per-cluster overrides. The
 * `me` / `counterparty` semantic colors (紫羅蘭 / 暖灰) are part of the
 * domain glossary and intentionally NOT customisable — overrides for
 * those speakers are silently ignored.
 *
 *   - default       : same 6 hues the original transcript-pane shipped
 *                     with (purple / green / orange / blue / yellow-green / red)
 *   - vivid         : same arc, higher chroma (more saturated accents)
 *   - pastel        : low-chroma soft tints, friendlier for prolonged reading
 *   - high-contrast : ≥65° hue separation + lower accent lightness, meets
 *                     WCAG non-text contrast guidance
 *   - grayscale     : achromatic ladder — for B&W printing / colour vision
 *                     deficiency users
 */

export const TRANSCRIPT_COLOR_SCHEME_IDS = [
  "default",
  "vivid",
  "pastel",
  "high-contrast",
  "grayscale",
] as const;

export type SchemeId = (typeof TRANSCRIPT_COLOR_SCHEME_IDS)[number];

export interface TranscriptColorScheme {
  /** 6-entry hue array (null for grayscale; resolver uses lightness ladder). */
  hues: (number | null)[];
  /** Optional 6-entry lightness ladder (grayscale only). */
  lightness?: number[];
  /** Default accent lightness for non-grayscale schemes. */
  accentL: number;
  /** Default accent chroma for non-grayscale schemes. */
  accentC: number;
  /** Default background tint lightness for non-grayscale schemes. */
  bgL: number;
  /** Default background tint chroma for non-grayscale schemes. */
  bgC: number;
}

export const TRANSCRIPT_COLOR_SCHEMES: Readonly<Record<SchemeId, TranscriptColorScheme>> = {
  default: {
    hues: [300, 150, 30, 240, 90, 0],
    accentL: 0.55,
    accentC: 0.18,
    bgL: 0.93,
    bgC: 0.06,
  },
  vivid: {
    hues: [330, 170, 50, 210, 110, 10],
    accentL: 0.62,
    accentC: 0.24,
    bgL: 0.92,
    bgC: 0.1,
  },
  pastel: {
    hues: [320, 160, 40, 230, 100, 5],
    accentL: 0.78,
    accentC: 0.08,
    bgL: 0.96,
    bgC: 0.04,
  },
  "high-contrast": {
    hues: [280, 130, 25, 215, 95, 355],
    accentL: 0.42,
    accentC: 0.2,
    bgL: 0.9,
    bgC: 0.08,
  },
  grayscale: {
    hues: [null, null, null, null, null, null],
    lightness: [0.72, 0.58, 0.45, 0.32, 0.85, 0.2],
    accentL: 0.5, // unused for grayscale (resolver picks from `lightness`)
    accentC: 0,
    bgL: 0.93,
    bgC: 0,
  },
};

export interface TranscriptColorPref {
  scheme: SchemeId;
  /**
   * cluster N (1-indexed) → hue in `[0, 360)`.
   *
   * Slice-16 task 10.1: was previously a full color string, but using
   * the swatch's "accent" oklch as both accent + background tint made
   * cluster background and text bleed into the same colour. Storing a
   * pure hue lets the resolver compute accent + background from the
   * active scheme's `accentL/accentC/bgL/bgC` constants, preserving
   * the readability contrast across all schemes.
   *
   * The `grayscale` scheme ignores overrides entirely — its lightness
   * ladder doesn't have a meaningful hue to swap.
   */
  overrides: Record<number, number>;
}

const _DEFAULT_PREF: TranscriptColorPref = {
  scheme: "default",
  overrides: {},
};

const _CLUSTER_RE = /^speaker_cluster_(\d+|unknown)$/;

function _isValidHue(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value < 360;
}

export function parseTranscriptColorPref(raw: string | null): TranscriptColorPref {
  if (!raw) return { ..._DEFAULT_PREF, overrides: {} };
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return { ..._DEFAULT_PREF, overrides: {} };
    }
    const scheme = (TRANSCRIPT_COLOR_SCHEME_IDS as readonly string[]).includes(parsed.scheme)
      ? (parsed.scheme as SchemeId)
      : "default";
    const overrides: Record<number, number> = {};
    if (
      parsed.overrides &&
      typeof parsed.overrides === "object" &&
      !Array.isArray(parsed.overrides)
    ) {
      for (const [k, v] of Object.entries(parsed.overrides as Record<string, unknown>)) {
        const n = Number.parseInt(k, 10);
        // Slice-16 task 10.1: hue numbers only. Reject legacy string
        // overrides and out-of-range values fail-soft.
        if (Number.isFinite(n) && n >= 1 && _isValidHue(v)) {
          overrides[n] = v as number;
        }
      }
    }
    return { scheme, overrides };
  } catch {
    return { ..._DEFAULT_PREF, overrides: {} };
  }
}

export interface ClusterColor {
  background: string;
  accent: string;
}

/**
 * Map a transcript chunk's speaker label to its background tint + accent.
 *
 * Precedence:
 *   1. me / counterparty → semantic CSS vars (always; pref ignored)
 *   2. speaker_cluster_unknown → muted color (pref ignored)
 *   3. speaker_cluster_<N>:
 *      a. pref.overrides[N] if present → applies to both accent + bg
 *      b. scheme's hues[(N-1)%6] → derive accent + bg from scheme constants
 *      c. grayscale special-case: use lightness ladder, zero chroma
 *   4. unknown label → fallback (muted-foreground accent + transparent bg)
 */
export function _resolveClusterColor(speaker: string, pref: TranscriptColorPref): ClusterColor {
  if (speaker === "me") {
    return {
      background: `color-mix(in oklch, var(--color-me-soft) calc(var(--me-tint-alpha) * 1000%), transparent)`,
      accent: "var(--color-me)",
    };
  }
  if (speaker === "counterparty") {
    return {
      background: `color-mix(in oklch, var(--color-them-soft) calc(var(--them-tint-alpha) * 1000%), transparent)`,
      accent: "var(--color-them)",
    };
  }
  const match = _CLUSTER_RE.exec(speaker);
  if (!match) {
    return { background: "transparent", accent: "var(--color-muted-foreground)" };
  }
  if (match[1] === "unknown") {
    return {
      background: `color-mix(in oklch, var(--color-muted) calc(var(--them-tint-alpha) * 1000%), transparent)`,
      accent: "var(--color-muted-foreground)",
    };
  }
  const n = Number.parseInt(match[1] as string, 10);
  const scheme = TRANSCRIPT_COLOR_SCHEMES[pref.scheme];

  // Slice-16 task 10.1: grayscale always uses its lightness ladder;
  // overrides are intentionally ignored (no meaningful hue to swap).
  if (pref.scheme === "grayscale") {
    const lightness = scheme.lightness ?? scheme.hues.map(() => 0.5);
    const l = lightness[(n - 1) % lightness.length] ?? 0.5;
    return {
      accent: `oklch(${(l * 0.7).toFixed(3)} 0 0)`,
      background: `color-mix(in oklch, oklch(${l.toFixed(3)} 0 0) calc(var(--them-tint-alpha) * 1000%), transparent)`,
    };
  }

  // Override (when present) supplies the hue; accent + bg lightness/chroma
  // come from the active scheme so the contrast invariant holds.
  const override = pref.overrides[n];
  const hue =
    typeof override === "number" && override >= 0 && override < 360
      ? override
      : (scheme.hues[(n - 1) % scheme.hues.length] ?? 0);
  return {
    accent: `oklch(${scheme.accentL} ${scheme.accentC} ${hue})`,
    background: `color-mix(in oklch, oklch(${scheme.bgL} ${scheme.bgC} ${hue}) calc(var(--them-tint-alpha) * 1000%), transparent)`,
  };
}
