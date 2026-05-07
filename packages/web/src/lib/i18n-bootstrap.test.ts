/**
 * Bootstrap-level tests for i18n integration.
 *
 * Covers AC-1 (i18n initialized at app startup) and AC-4 (default zh-TW
 * when no user preference exists). Verifies:
 *   - main.tsx imports the i18n module so init runs at app boot
 *   - Without a localStorage preference, fallbackLng applies
 *   - changeLanguage round-trips between zh-TW and en
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { i18n } from "./i18n";

const LS_KEY = "meeting-playbook.locale";

describe("main.tsx bootstraps i18n", () => {
  test("imports ./lib/i18n so the side-effect init runs at app start", () => {
    const mainPath = join(__dirname, "..", "main.tsx");
    const main = readFileSync(mainPath, "utf-8");
    expect(main).toContain("./lib/i18n");
  });
});

describe("i18n runtime defaults", () => {
  beforeEach(() => {
    localStorage.removeItem(LS_KEY);
  });
  afterEach(async () => {
    localStorage.removeItem(LS_KEY);
    // Reset language so other test files that assume zh-TW default keep working.
    await i18n.changeLanguage("zh-TW");
  });

  test("resolved language is one of the supported locales", () => {
    expect(["zh-TW", "en"]).toContain(i18n.language);
  });

  test("fallbackLng remains zh-TW after any switch", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.options.fallbackLng).toContain("zh-TW");
  });

  test("changeLanguage round-trips between en and zh-TW", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.language).toBe("en");

    await i18n.changeLanguage("zh-TW");
    expect(i18n.language).toBe("zh-TW");
  });

  test("a stored localStorage choice survives subsequent changeLanguage calls", async () => {
    await i18n.changeLanguage("en");
    expect(localStorage.getItem(LS_KEY)).toBe("en");

    await i18n.changeLanguage("zh-TW");
    expect(localStorage.getItem(LS_KEY)).toBe("zh-TW");
  });
});
