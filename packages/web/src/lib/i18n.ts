/**
 * i18n initialization — react-i18next + browser language detector.
 *
 * Per ADR-0008 (TypeScript frontend) and ADR-0022 (zh-TW default + en):
 * - Detection chain: URL ?lng → cookie → localStorage → navigator
 * - Cached choice persists in localStorage under namespaced key
 * - fallbackLng = 'zh-TW'; supportedLngs = ['zh-TW', 'en']
 * - load = 'currentOnly' so zh-TW is not auto-stripped to zh
 * - Dev: missing keys log to console; prod: silent fallback to the key string
 *
 * Resource loading (locale JSON files) lives in `./i18n-resources` so this
 * module stays import-only-side-effect-free for tests that only assert config.
 */

import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "../locales/en.json";
import zhTW from "../locales/zh-TW.json";

const isDev = import.meta.env?.MODE !== "production";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "zh-TW",
    supportedLngs: ["zh-TW", "en"],
    load: "currentOnly",
    interpolation: {
      // React already escapes — disable i18next's escape to avoid double-encoding.
      escapeValue: false,
    },
    detection: {
      order: ["querystring", "cookie", "localStorage", "navigator"],
      lookupQuerystring: "lng",
      lookupLocalStorage: "meeting-playbook.locale",
      caches: ["localStorage"],
    },
    resources: {
      "zh-TW": { translation: zhTW },
      en: { translation: en },
    },
    saveMissing: isDev,
    missingKeyHandler: isDev
      ? (lngs, _ns, key) => {
          // eslint-disable-next-line no-console
          console.warn(`[i18n] missing key "${key}" for locale(s) ${lngs.join(",")}`);
        }
      : undefined,
  });

export { i18n };
