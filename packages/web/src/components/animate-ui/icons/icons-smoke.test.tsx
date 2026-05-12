/**
 * Smoke test — slice animate-ui-icons-swap task 2.1.
 *
 * Mounts every installed animate-ui icon and asserts the component
 * renders an `<svg>` root. This guards against a regression where a
 * registry icon file's import path or `motion/react` aliasing breaks
 * the build silently (the file would mount without rendering).
 *
 * 5 lucide icons proposed in the original 15-icon scope (mic, square,
 * shield, shield-check, languages) are NOT installed because the
 * animate-ui registry returns HTTP 404 for those names as of 2026-05.
 * The spec documents this gap; this test covers the 10 that DID install.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render } from "@testing-library/react";
import { ArrowLeft } from "./arrow-left";
import { Copy } from "./copy";
import { Download } from "./download";
import { Loader } from "./loader";
import { Lock } from "./lock";
import { LogOut } from "./log-out";
import { Plus } from "./plus";
import { RefreshCw } from "./refresh-cw";
import { Sparkles } from "./sparkles";
import { Trash } from "./trash";

afterEach(cleanup);

const ICONS = [
  ["arrow-left", ArrowLeft],
  ["copy", Copy],
  ["download", Download],
  ["loader", Loader],
  ["lock", Lock],
  ["log-out", LogOut],
  ["plus", Plus],
  ["refresh-cw", RefreshCw],
  ["sparkles", Sparkles],
  ["trash", Trash],
] as const;

describe("animate-ui icons smoke", () => {
  for (const [name, Icon] of ICONS) {
    test(`${name} renders an <svg> root`, () => {
      const { container } = render(<Icon />);
      const svg = container.querySelector("svg");
      expect(svg).not.toBeNull();
    });
  }
});
