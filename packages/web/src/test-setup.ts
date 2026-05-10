/**
 * bun test preload.
 *
 * 1. Registers happy-dom so React Testing Library can render components.
 * 2. Initializes i18n singleton (default zh-TW).
 *
 * Slice-7 round 2 cleanup: dropped the MarkdownEditor (TipTap) stub —
 * the editor has been reverted to a plain `<textarea>` plus a
 * `<MarkdownPreview>` (react-markdown) read-only view, both of which
 * happy-dom handles natively.
 */

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();

const { i18n } = await import("./lib/i18n");
await i18n.changeLanguage("zh-TW");
