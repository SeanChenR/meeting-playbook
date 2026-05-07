/**
 * bun test preload.
 *
 * 1. Registers happy-dom as the test environment so React Testing Library
 *    can render components against a DOM.
 * 2. Initializes the i18n singleton and forces it to zh-TW. Without this,
 *    tests would inherit happy-dom's `navigator.language` (often "en-US"),
 *    making locale-sensitive assertions flaky. Tests that need to verify
 *    en behavior call `i18n.changeLanguage("en")` themselves.
 */

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();

const { i18n } = await import("./lib/i18n");
await i18n.changeLanguage("zh-TW");
