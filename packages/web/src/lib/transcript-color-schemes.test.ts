/**
 * Tests for transcript-color-schemes — slice-16 task 6.1.
 *
 * Eight scenarios per task description:
 *   (a) default scheme cluster 1/2 → accent uses hue 300 / 150
 *   (b) override shadows scheme palette
 *   (c) grayscale cluster 2 → zero-chroma oklch
 *   (d) speaker="me" + overrides[1] → still var(--color-me) (pref ignored)
 *   (e) speaker="counterparty" + grayscale → still var(--color-them)
 *   (f) speaker_cluster_unknown → muted, overrides ignored
 *   (g) malformed JSON → default
 *   (h) wrong shape JSON → default
 */

import { describe, expect, test } from "bun:test";

import {
  TRANSCRIPT_COLOR_SCHEMES,
  TRANSCRIPT_COLOR_SCHEME_IDS,
  _resolveClusterColor,
  parseTranscriptColorPref,
  type TranscriptColorPref,
} from "./transcript-color-schemes";

const _DEFAULT_PREF: TranscriptColorPref = { scheme: "default", overrides: {} };

describe("_resolveClusterColor", () => {
  test("(a) default scheme: cluster 1 → hue 300; cluster 2 → hue 150", () => {
    const c1 = _resolveClusterColor("speaker_cluster_1", _DEFAULT_PREF);
    expect(c1.accent).toContain("300");
    const c2 = _resolveClusterColor("speaker_cluster_2", _DEFAULT_PREF);
    expect(c2.accent).toContain("150");
  });

  test("(b) hue-number override shadows scheme palette (slice-16 task 10.1)", () => {
    const pref: TranscriptColorPref = {
      scheme: "vivid",
      overrides: { 3: 200 },
    };
    const c3 = _resolveClusterColor("speaker_cluster_3", pref);
    // accent uses the vivid scheme's accentL/accentC but hue 200 (override).
    expect(c3.accent).toContain("200");
    // background is a light tint of the same hue.
    expect(c3.background).toContain("200");
  });

  test("(b2) grayscale scheme ignores any override (slice-16 task 10.1)", () => {
    const pref: TranscriptColorPref = {
      scheme: "grayscale",
      overrides: { 2: 180 },
    };
    const c = _resolveClusterColor("speaker_cluster_2", pref);
    // chroma stays 0 regardless of override.
    expect(c.accent).toMatch(/^oklch\([\d.]+ 0 0\)$/);
  });

  test("(c) grayscale cluster 2 → zero-chroma oklch accent", () => {
    const pref: TranscriptColorPref = { scheme: "grayscale", overrides: {} };
    const c = _resolveClusterColor("speaker_cluster_2", pref);
    // accent uses oklch(<L> 0 0) — chroma exactly 0
    expect(c.accent).toMatch(/^oklch\([\d.]+ 0 0\)$/);
    expect(c.background).toContain("0 0");
  });

  test("(d) me + overrides[1] → still var(--color-me)", () => {
    const pref: TranscriptColorPref = {
      scheme: "vivid",
      overrides: { 1: "#ff0000" },
    };
    const c = _resolveClusterColor("me", pref);
    expect(c.accent).toBe("var(--color-me)");
  });

  test("(e) counterparty + grayscale → still var(--color-them)", () => {
    const pref: TranscriptColorPref = { scheme: "grayscale", overrides: {} };
    const c = _resolveClusterColor("counterparty", pref);
    expect(c.accent).toBe("var(--color-them)");
  });

  test("me speaker accent is a token reference, not a hardcoded oklch literal", () => {
    // P1 `ui-overhaul-aura-tokens` task 4.4: after the token block rewrite
    // the me/them speaker accents MUST stay token-driven so dark/light parity
    // is invariant — they must NOT short-circuit to hardcoded oklch strings.
    const c = _resolveClusterColor("me", _DEFAULT_PREF);
    expect(c.accent).toBe("var(--color-me)");
    expect(c.accent).not.toMatch(/^oklch\(/i);
    expect(c.background).toContain("var(--color-me-soft)");
  });

  test("counterparty speaker accent is a token reference, not a hardcoded oklch literal", () => {
    // P1 `ui-overhaul-aura-tokens` task 4.4: them ditto — pinned to the
    // `--color-them` token so the magenta hue swap propagates through.
    const c = _resolveClusterColor("counterparty", _DEFAULT_PREF);
    expect(c.accent).toBe("var(--color-them)");
    expect(c.accent).not.toMatch(/^oklch\(/i);
    expect(c.background).toContain("var(--color-them-soft)");
  });

  test("(f) speaker_cluster_unknown → muted; overrides ignored", () => {
    const pref: TranscriptColorPref = {
      scheme: "default",
      overrides: { 1: "#ff0000" }, // would touch cluster_1, not unknown
    };
    const c = _resolveClusterColor("speaker_cluster_unknown", pref);
    expect(c.accent).toBe("var(--color-muted-foreground)");
    expect(c.background).toContain("var(--color-muted)");
  });
});

describe("parseTranscriptColorPref", () => {
  test("(g) malformed JSON → default", () => {
    const p = parseTranscriptColorPref("{not-valid-json");
    expect(p.scheme).toBe("default");
    expect(p.overrides).toEqual({});
  });

  test("(h) wrong-shape JSON → default", () => {
    const p = parseTranscriptColorPref('{"scheme":"weird","overrides":[]}');
    expect(p.scheme).toBe("default");
    expect(p.overrides).toEqual({});
  });

  test("(h2) legacy string override is dropped on parse (slice-16 task 10.1)", () => {
    const raw = JSON.stringify({
      scheme: "default",
      overrides: { "2": "oklch(0.55 0.18 150)" },
    });
    const p = parseTranscriptColorPref(raw);
    expect(p.scheme).toBe("default"); // scheme survives
    expect(p.overrides["2"]).toBeUndefined(); // string value rejected
  });

  test("(h3) out-of-range hue is dropped on parse (slice-16 task 10.1)", () => {
    const raw = JSON.stringify({
      scheme: "vivid",
      overrides: { "1": 360, "2": -5, "3": 200 },
    });
    const p = parseTranscriptColorPref(raw);
    expect(p.overrides["1"]).toBeUndefined();
    expect(p.overrides["2"]).toBeUndefined();
    expect(p.overrides["3"]).toBe(200);
  });

  test("null raw → default", () => {
    const p = parseTranscriptColorPref(null);
    expect(p.scheme).toBe("default");
  });

  test("valid scheme + hue-number overrides round-trip", () => {
    const raw = JSON.stringify({
      scheme: "pastel",
      overrides: { "2": 120 },
    });
    const p = parseTranscriptColorPref(raw);
    expect(p.scheme).toBe("pastel");
    expect(p.overrides[2]).toBe(120);
  });
});

describe("scheme catalogue invariants", () => {
  test("each scheme has 6 hue entries (grayscale has 6 nulls)", () => {
    for (const id of TRANSCRIPT_COLOR_SCHEME_IDS) {
      const scheme = TRANSCRIPT_COLOR_SCHEMES[id];
      expect(scheme.hues.length).toBe(6);
    }
  });

  test("default scheme matches the legacy _CLUSTER_HUES array", () => {
    expect(TRANSCRIPT_COLOR_SCHEMES.default.hues).toEqual([300, 150, 30, 240, 90, 0]);
  });
});
