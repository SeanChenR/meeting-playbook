/**
 * bun test preload — registers happy-dom as the test environment so React
 * Testing Library can render components against a DOM.
 */

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();
