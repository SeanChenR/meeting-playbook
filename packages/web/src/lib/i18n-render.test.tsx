/**
 * AC-8 — sample component renders correctly under both locales.
 * AC-9 — missing-key behavior re-asserted as a self-evidence test.
 *
 * This file is the canonical "if you change i18n, the slice still works"
 * smoke test referenced by Issue #4 acceptance criteria.
 */

import { afterEach, beforeEach, describe, expect, spyOn, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { useTranslation } from "react-i18next";
import { i18n } from "./i18n";

/** Tiny inline component used purely for the AC-8 smoke check. */
function Greeting() {
  const { t } = useTranslation();
  return <p data-testid="sample-greeting">{t("auth.shell.subhead")}</p>;
}

describe("Sample component renders under both locales (AC-8)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });
  afterEach(async () => {
    cleanup();
    await i18n.changeLanguage("zh-TW");
  });

  test("zh-TW renders the Chinese subhead", () => {
    render(<Greeting />);
    expect(screen.getByTestId("sample-greeting").textContent).toBe("個人 AI 會議助理");
  });

  test("en renders the English subhead after changeLanguage", async () => {
    await i18n.changeLanguage("en");
    render(<Greeting />);
    expect(screen.getByTestId("sample-greeting").textContent).toBe("Personal AI meeting assistant");
  });
});

describe("Missing-key behavior — re-assertion (AC-9)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("zh-TW");
  });

  test("requesting a non-existent key returns the key itself", () => {
    const result = i18n.t("auth.this_key_definitely_does_not_exist");
    expect(result).toBe("auth.this_key_definitely_does_not_exist");
  });

  test("missingKeyHandler logs to console.warn", () => {
    const warnSpy = spyOn(console, "warn").mockImplementation(() => {});
    i18n.t("auth.another_missing_for_warn_check");
    expect(warnSpy.mock.calls.some((c) => String(c[0]).includes("[i18n] missing key"))).toBe(true);
    warnSpy.mockRestore();
  });
});
