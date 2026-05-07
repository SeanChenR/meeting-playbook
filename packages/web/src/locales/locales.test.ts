/**
 * Locale-file integrity tests (AC-2, AC-9).
 *
 * Two invariants protected by these tests:
 *  1. Every locale file has the same key tree (no key may live in only one
 *     locale). This is the contract documented in CLAUDE.md.
 *  2. Both files contain the three top-level groups required by design:
 *     `common`, `auth`, `errors`.
 *
 * If a future PR adds a key to one locale but forgets the other, the
 * deep-equal check below fails before the change can land.
 */

import { describe, expect, test } from "bun:test";
import en from "./en.json";
import zhTW from "./zh-TW.json";

type AnyJson = Record<string, unknown>;

/** Recursively collect the set of dot-paths in a JSON object. */
function collectPaths(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return [prefix];
  }
  const o = obj as AnyJson;
  return Object.keys(o)
    .sort()
    .flatMap((k) => collectPaths(o[k], prefix ? `${prefix}.${k}` : k));
}

describe("locale files mirror each other", () => {
  test("both files have identical key trees", () => {
    const zhPaths = collectPaths(zhTW);
    const enPaths = collectPaths(en);
    expect(zhPaths).toEqual(enPaths);
  });

  test("both files declare exactly the three required top-level groups", () => {
    expect(Object.keys(zhTW as AnyJson).sort()).toEqual(["auth", "common", "errors"]);
    expect(Object.keys(en as AnyJson).sort()).toEqual(["auth", "common", "errors"]);
  });
});
