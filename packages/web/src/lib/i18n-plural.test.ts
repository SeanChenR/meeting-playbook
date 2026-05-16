/**
 * Verify the en `settings.tags.deleteConfirm.description` key uses ICU
 * plural correctly — count=1 emits "1 meeting" (singular), count=5 emits
 * "5 meetings" (plural). Implemented via i18next's plural-suffix
 * convention (`description_one` / `description_other`).
 *
 * Per slice-17 task 6.3 spec + Example table.
 */

import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import en from "../locales/en.json";
import zhTW from "../locales/zh-TW.json";

const _i18n = i18next.createInstance();
_i18n.init({
  lng: "en",
  fallbackLng: "en",
  defaultNS: "translation",
  resources: {
    en: { translation: en },
    "zh-TW": { translation: zhTW },
  },
  interpolation: { escapeValue: false },
});

describe("settings.tags.deleteConfirm.description plural form (en)", () => {
  test("count=1 renders the singular form '1 meeting'", () => {
    const result = _i18n.t("settings.tags.deleteConfirm.description", {
      count: 1,
      lng: "en",
    });
    expect(result).toContain("1 meeting");
    expect(result).not.toContain("1 meetings");
  });

  test("count=5 renders the plural form '5 meetings'", () => {
    const result = _i18n.t("settings.tags.deleteConfirm.description", {
      count: 5,
      lng: "en",
    });
    expect(result).toContain("5 meetings");
  });
});

describe("settings.tags.deleteConfirm.description plural form (zh-TW)", () => {
  test("zh-TW uses the same form regardless of count", () => {
    const a = _i18n.t("settings.tags.deleteConfirm.description", {
      count: 1,
      lng: "zh-TW",
    });
    const b = _i18n.t("settings.tags.deleteConfirm.description", {
      count: 5,
      lng: "zh-TW",
    });
    expect(a).toContain("1 個會議");
    expect(b).toContain("5 個會議");
  });
});
