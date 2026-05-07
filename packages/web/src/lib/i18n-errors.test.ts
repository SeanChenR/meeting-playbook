/**
 * AC-7 — localizedErrorMessage helper.
 *
 * Backend returns `{error_code, message}`. The frontend looks up
 * `errors.<error_code>` in the current locale. If the code is unknown,
 * fall back to `errors.common.unknown` (also localized).
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { i18n } from "./i18n";
import { localizedErrorMessage } from "./i18n-errors";

describe("localizedErrorMessage", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });
  afterEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });

  test("returns the zh-TW string for a known auth.gateway_bypass code", () => {
    expect(localizedErrorMessage("auth.gateway_bypass", i18n.t.bind(i18n))).toBe(
      "請從正確的入口登入",
    );
  });

  test("returns the en string for the same code after switching locale", async () => {
    await i18n.changeLanguage("en");
    expect(localizedErrorMessage("auth.gateway_bypass", i18n.t.bind(i18n))).toBe(
      "Please sign in through the gateway",
    );
  });

  test("falls back to errors.common.unknown when the code is not in the locale", () => {
    expect(localizedErrorMessage("definitely.not.a.real.code", i18n.t.bind(i18n))).toBe(
      "發生未知錯誤",
    );
  });

  test("fallback also follows the current locale", async () => {
    await i18n.changeLanguage("en");
    expect(localizedErrorMessage("not.a.real.code", i18n.t.bind(i18n))).toBe(
      "An unknown error occurred",
    );
  });
});
