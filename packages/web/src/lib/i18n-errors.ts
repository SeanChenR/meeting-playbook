/**
 * Map a backend `error_code` to a localized message.
 *
 * Conventions (per ADR-0022 + slice-02 design):
 *   - Backend returns `{ error_code: "auth.gateway_bypass", message: "..." }`
 *   - Frontend looks up `errors.<error_code>` in the current locale
 *   - If the key is missing, fall back to `errors.common.unknown`
 *
 * The helper accepts the i18n `t` function rather than importing it directly
 * so call sites can pass their component-scoped `t` from `useTranslation()`.
 */

import type { TFunction } from "i18next";

export function localizedErrorMessage(
  errorCode: string,
  t: TFunction,
  params?: Record<string, unknown>,
): string {
  const key = `errors.${errorCode}`;
  // i18next returns the key string when missing; we override with the
  // locale's `errors.common.unknown` so the user sees something sensible.
  const fallback = t("errors.common.unknown");
  // `params` keys are spread as i18next interpolation vars (e.g. {{dropped}});
  // callers MUST NOT pass `defaultValue` here — we set it ourselves.
  const resolved = t(key, { defaultValue: fallback, ...params });
  return typeof resolved === "string" && resolved !== key ? resolved : fallback;
}
