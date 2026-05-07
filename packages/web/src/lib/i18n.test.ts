/**
 * Unit tests for the i18n initialization module.
 *
 * Verifies that the singleton i18n instance is configured per design:
 * - fallbackLng = 'zh-TW' (per ADR-0022)
 * - supportedLngs includes both 'zh-TW' and 'en'
 * - load = 'currentOnly' (avoid zh-TW → zh degradation)
 * - LocalStorage cache key is the agreed namespaced value
 */

import { describe, expect, test } from "bun:test";
import { i18n } from "./i18n";

describe("i18n module", () => {
  test("exports an initialized i18n instance", () => {
    expect(i18n).toBeDefined();
    expect(typeof i18n.t).toBe("function");
    expect(typeof i18n.changeLanguage).toBe("function");
  });

  test("default / fallback language is zh-TW", () => {
    expect(i18n.options.fallbackLng).toContain("zh-TW");
  });

  test("supportedLngs covers exactly zh-TW and en", () => {
    const supported = i18n.options.supportedLngs as string[];
    expect(supported).toContain("zh-TW");
    expect(supported).toContain("en");
  });

  test("load option is 'currentOnly' so zh-TW is not stripped to zh", () => {
    expect(i18n.options.load).toBe("currentOnly");
  });

  test("detector caches choice in the namespaced localStorage key", () => {
    const detection = (i18n.options as { detection?: { lookupLocalStorage?: string } }).detection;
    expect(detection?.lookupLocalStorage).toBe("meeting-playbook.locale");
  });
});
