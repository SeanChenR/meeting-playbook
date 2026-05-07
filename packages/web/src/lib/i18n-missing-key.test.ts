/**
 * AC-2 + AC-9: missing-key behavior.
 *
 * Two contracts under test:
 *   1. Asking for a key that exists in zh-TW but not en falls back to the
 *      zh-TW value (because fallbackLng = 'zh-TW').
 *   2. Asking for a key that exists in NO locale invokes the
 *      missingKeyHandler (which console.warn's in dev).
 */

import { afterAll, beforeAll, beforeEach, describe, expect, spyOn, test } from "bun:test";
import { i18n } from "./i18n";

describe("missing-key behavior", () => {
  beforeAll(async () => {
    // Seed a key only in zh-TW so we can prove the en→zh-TW fallback path.
    i18n.addResource("zh-TW", "translation", "common.testZhOnly", "僅中文");
  });

  afterAll(() => {
    // Original resources are re-installed at file load via i18n.init resources;
    // we only added a single key, leaving it in place is harmless for cross-file tests.
  });

  beforeEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });
  afterAll(async () => {
    // Reset so cross-file tests do not inherit a non-zh-TW default.
    await i18n.changeLanguage("zh-TW");
  });

  test("when a key lives only in zh-TW, requesting it under en falls back to zh-TW value", async () => {
    await i18n.changeLanguage("en");
    const value = i18n.t("common.testZhOnly");
    expect(value).toBe("僅中文");
  });

  test("requesting a key that exists in no locale returns the key string itself", () => {
    const fakeKey = "common.this_key_does_not_exist_xyz_123";
    const value = i18n.t(fakeKey);
    expect(value).toBe(fakeKey);
  });

  test("missing keys trigger the missingKeyHandler (console.warn) in dev", () => {
    const warnSpy = spyOn(console, "warn").mockImplementation(() => {});

    i18n.t("common.another_missing_key_for_warn_test");

    // Either saveMissing fires the handler immediately, or it queues —
    // assert that at least one warn happened OR was scheduled.
    // Since saveMissing=true in dev, handler runs synchronously.
    expect(warnSpy.mock.calls.some((c) => String(c[0]).includes("[i18n] missing key"))).toBe(true);

    warnSpy.mockRestore();
  });
});
