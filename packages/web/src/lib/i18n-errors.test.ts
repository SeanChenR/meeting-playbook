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

  test("meeting_link.* error codes resolve to the locale-specific message", async () => {
    expect(localizedErrorMessage("meeting_link.duplicate", i18n.t.bind(i18n))).toBe(
      "這兩個會議已經連結了",
    );
    expect(localizedErrorMessage("meeting_link.self_reference", i18n.t.bind(i18n))).toBe(
      "不能連結自己",
    );
    expect(localizedErrorMessage("meeting_link.not_found", i18n.t.bind(i18n))).toBe("找不到此關聯");

    await i18n.changeLanguage("en");
    expect(localizedErrorMessage("meeting_link.duplicate", i18n.t.bind(i18n))).toBe(
      "These meetings are already linked",
    );
  });

  test("attachment.staging_batch_truncated interpolates dropped + accepted counts (zh-TW)", () => {
    expect(
      localizedErrorMessage("attachment.staging_batch_truncated", i18n.t.bind(i18n), {
        dropped: 5,
        accepted: 2,
      }),
    ).toBe("拖入 5 個檔，配額只上傳前 2 個");
  });

  test("attachment.staging_batch_truncated interpolates dropped + accepted counts (en)", async () => {
    await i18n.changeLanguage("en");
    expect(
      localizedErrorMessage("attachment.staging_batch_truncated", i18n.t.bind(i18n), {
        dropped: 5,
        accepted: 2,
      }),
    ).toBe("Dropped 5 files, only the first 2 fit the staging quota");
  });
});
