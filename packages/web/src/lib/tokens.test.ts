/**
 * Design token validation smoke test — change `ui-overhaul-aura-tokens` D10.
 *
 * Guards three invariants that hand-rolled review can drift on:
 *
 *   1. Every `--color-*` declaration in `packages/web/src/index.css` has a
 *      value that starts with `oklch(`, `var(--color-`, or a permitted CSS
 *      keyword (`none`, `transparent`).
 *   2. The set of `--color-*` keys declared inside `[data-theme="dark"]`
 *      equals the set declared inside the `[data-theme="light"]` /
 *      `:root` block (dark/light parity — no theme is missing a token the
 *      other has).
 *   3. No `*.ts` / `*.tsx` file under `packages/web/src/` (except the explicit
 *      allowlist below) contains a raw hex literal (`#[0-9a-fA-F]{3,8}`) or
 *      `rgb(` / `rgba(` colour string in source code. Test files are
 *      excluded — fixtures freely include `#hex` colours for tag tests etc.
 *
 * Spec ref: `openspec/changes/ui-overhaul-aura-tokens/specs/ui-design-system/spec.md`
 *           — "oklch validation smoke test SHALL guard token format and
 *           dark/light parity"
 */

import { describe, expect, test } from "bun:test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const REPO_WEB_SRC = path.resolve(import.meta.dir, "..");
const INDEX_CSS = path.join(REPO_WEB_SRC, "index.css");

/**
 * Files that are permitted to contain raw hex literals or rgb/rgba strings
 * in source code, with the justification stated inline. Adding a new entry
 * MUST be paired with a `// reason:` comment so reviewers see the rationale.
 *
 * Paths are repo-relative to `packages/web/src/`.
 */
const RAW_COLOR_ALLOWLIST: ReadonlyArray<{ file: string; reason: string }> = [
  {
    // reason: tag-palette is an isolated palette domain — the 9 swatch
    // colours and the `pickReadableTextColor` foreground threshold are
    // computed against fixed hex values per slice-17 design. Migrating
    // these to oklch would change palette identities. Out of scope for
    // ui-overhaul-aura-tokens (token block change only).
    file: "lib/tag-palette.ts",
    reason: "isolated tag palette domain — fixed hex swatches per slice-17",
  },
  {
    // reason: CSS mask alpha context. The `linear-gradient(#000 0 0)`
    // string inside `WebkitMask` is a mask alpha layer, not a visual
    // colour — `#000` here means "fully opaque" in the mask channel and
    // is not consumed as a foreground/background colour. oklch is not
    // well supported inside `mask` declarations across browsers.
    file: "components/magicui/border-beam.tsx",
    reason: "CSS mask alpha context — `#000` means opaque, not a visual colour",
  },
  {
    // reason: Google brand SVG fill values. The Google sign-in button
    // SVG uses Google's brand-mandated hex colours (#4285F4 / #34A853 /
    // #FBBC05 / #EA4335). Brand assets are an explicit exception in
    // DESIGN.md §2 — they must NOT be remapped to project tokens.
    file: "routes/login.tsx",
    reason: "Google brand SVG fill — brand asset, not a project colour",
  },
  {
    // reason: same Google brand SVG, duplicated on the linked-accounts
    // section of the profile page. Same justification as login.tsx.
    file: "routes/settings/profile.tsx",
    reason: "Google brand SVG fill — brand asset, not a project colour",
  },
  {
    // reason: tag chip readability is a function of the (theme-invariant)
    // tag colour, not the app theme. `text-[#1a1a1a]` matches DARK_FG_HEX
    // in `lib/tag-palette.ts` — the constant used by `pickReadableTextColor`
    // to compute contrast. Using `text-(--color-foreground)` here breaks in
    // dark mode where `--color-foreground` is bone-white (`#EDECEE`) and
    // becomes invisible on the light-end TAG_PALETTE swatches.
    file: "components/tags/tag-chip.tsx",
    reason: "theme-invariant dark text matches tag-palette DARK_FG_HEX (#1a1a1a)",
  },
];

const ALLOWLIST_FILES = new Set(RAW_COLOR_ALLOWLIST.map((entry) => entry.file));

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
// Match `rgb(` / `rgba(` anywhere — note we deliberately omit `\b` since
// Tailwind v4 arbitrary-value syntax (e.g. `shadow-[0_1px_2px_0_rgb(...)]`)
// embeds the call after an underscore, which is a word character in JS regex
// and would otherwise prevent the word boundary from matching.
const RGB_RE = /rgba?\(/i;
// Test files freely use #hex for tag fixtures, mock data, snapshot strings.
// Production source must use tokens.
const IS_TEST_FILE = (filename: string): boolean =>
  /\.test\.(ts|tsx)$/.test(filename) || filename.endsWith(".d.ts");
const IS_SOURCE_EXT = (filename: string): boolean =>
  filename.endsWith(".ts") || filename.endsWith(".tsx");

function _listSourceFiles(root: string): string[] {
  const out: string[] = [];
  function walk(dir: string) {
    for (const entry of readdirSync(dir)) {
      const abs = path.join(dir, entry);
      const st = statSync(abs);
      if (st.isDirectory()) {
        if (entry === "node_modules" || entry === "dist" || entry.startsWith(".")) continue;
        walk(abs);
      } else if (IS_SOURCE_EXT(entry) && !IS_TEST_FILE(entry)) {
        out.push(abs);
      }
    }
  }
  walk(root);
  return out;
}

interface ParsedTokenBlock {
  /** Block label for error messages — e.g. `[data-theme="dark"]`. */
  label: string;
  /** Token names declared in this block (without leading `--`). */
  tokens: Map<string, string>;
}

/**
 * Permitted value shapes for `--color-*` token declarations:
 *   - `oklch(<L> <C> <H> [/ <alpha>])` where L/C/H may be literals OR nested
 *     `var(--primary-hue)` knob references (one level of nesting).
 *   - `var(--color-...)` aliases.
 *   - The CSS keywords `none` / `transparent`.
 *
 * We deliberately don't try to fully parse the oklch arg list — a simple
 * "starts with `oklch(` and ends with `)`" check after stripping nested
 * `var(...)` calls is enough to reject raw hex / rgb sneaking into the
 * token catalogue without false-positive-ing on legitimate knob refs.
 */
function _isPermittedTokenValue(rawValue: string): boolean {
  const value = rawValue.trim();
  if (value === "none" || value === "transparent") return true;
  if (/^var\(--color-[a-z0-9-]+\)$/i.test(value)) return true;
  // Collapse nested var(...) calls so a simple oklch( ... ) check works.
  const collapsed = value.replace(/var\([^)]*\)/g, "0");
  return /^oklch\([^()]*\)$/i.test(collapsed);
}

function _stripCssComments(css: string): string {
  // Strip /* ... */ comments before block matching — without this the comment
  // text bleeds into the selector heading (since `*/` is followed by the next
  // selector on a separate line, and our `[^{}]+` heading regex is greedy).
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function _parseColorBlocks(rawCss: string): ParsedTokenBlock[] {
  // Capture each top-level block by selector heading and its contents.
  // We restrict to the three relevant blocks: `:root,[data-theme="light"]`,
  // `[data-theme="dark"]`. The parser is intentionally simple — selectors
  // sit on a single line followed by `{ ... }` with nested rules forbidden
  // at this depth in our index.css (verified by the file structure).
  const css = _stripCssComments(rawCss);
  const blocks: ParsedTokenBlock[] = [];
  const blockRe = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = blockRe.exec(css)) !== null) {
    const heading = match[1]?.trim();
    const body = match[2] ?? "";
    if (!heading) continue;
    if (
      heading.includes('[data-theme="dark"]') ||
      heading.includes('[data-theme="light"]') ||
      heading === ":root" ||
      heading.startsWith(":root,") ||
      heading.startsWith(":root ,")
    ) {
      const tokens = new Map<string, string>();
      const declRe = /--color-([a-z0-9-]+)\s*:\s*([^;]+);/gi;
      let dmatch: RegExpExecArray | null;
      while ((dmatch = declRe.exec(body)) !== null) {
        const name = dmatch[1] ?? "";
        const value = (dmatch[2] ?? "").trim();
        tokens.set(name, value);
      }
      blocks.push({ label: heading, tokens });
    }
  }
  return blocks;
}

describe("design tokens — index.css", () => {
  const css = readFileSync(INDEX_CSS, "utf-8");
  const blocks = _parseColorBlocks(css);
  // The "light" block is the one that declares `--color-*` tokens AND
  // matches `[data-theme="light"]` (its selector is `:root, [data-theme="light"]`
  // so an `includes` check is sufficient). Skip the bare `:root` block that
  // only carries typography / spacing tokens.
  const lightBlock = blocks.find(
    (b) => b.label.includes('[data-theme="light"]') && b.tokens.size > 0,
  );
  const darkBlock = blocks.find(
    (b) => b.label.includes('[data-theme="dark"]') && b.tokens.size > 0,
  );

  test("light and dark theme blocks are both present", () => {
    expect(lightBlock).toBeDefined();
    expect(darkBlock).toBeDefined();
  });

  test("every --color-* value matches the permitted oklch / var / keyword pattern", () => {
    const violations: string[] = [];
    for (const block of blocks) {
      for (const [name, value] of block.tokens.entries()) {
        if (!_isPermittedTokenValue(value)) {
          violations.push(`${block.label} --color-${name}: ${value}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });

  test("dark theme and light theme declare identical --color-* token keys", () => {
    if (!lightBlock || !darkBlock) throw new Error("missing block");
    const lightKeys = new Set(lightBlock.tokens.keys());
    const darkKeys = new Set(darkBlock.tokens.keys());
    const lightOnly = [...lightKeys].filter((k) => !darkKeys.has(k));
    const darkOnly = [...darkKeys].filter((k) => !lightKeys.has(k));
    expect({ lightOnly, darkOnly }).toEqual({ lightOnly: [], darkOnly: [] });
  });

  test("--color-info and --color-me are both declared as literal oklch values in each theme", () => {
    if (!lightBlock || !darkBlock) throw new Error("missing block");
    for (const block of [lightBlock, darkBlock]) {
      const info = block.tokens.get("info");
      const me = block.tokens.get("me");
      expect(info).toBeDefined();
      expect(me).toBeDefined();
      // Info must be its own oklch(...) declaration, NOT a `var(--color-me)`
      // alias, so the speaker semantic and the status semantic can diverge.
      expect(info ?? "").toMatch(/^oklch\(/i);
      expect(me ?? "").toMatch(/^oklch\(/i);
    }
  });

  test("--color-accent is a literal oklch value, not a var(--color-primary) alias", () => {
    if (!lightBlock || !darkBlock) throw new Error("missing block");
    for (const block of [lightBlock, darkBlock]) {
      const accent = block.tokens.get("accent");
      expect(accent).toBeDefined();
      expect(accent ?? "").toMatch(/^oklch\(/i);
    }
  });

  test("required token catalogue is present in both themes", () => {
    if (!lightBlock || !darkBlock) throw new Error("missing block");
    const required = [
      "background",
      "surface",
      "surface-2",
      "surface-3",
      "foreground",
      "muted-foreground",
      "subtle-foreground",
      "border",
      "border-strong",
      "primary",
      "primary-hover",
      "primary-soft",
      "primary-foreground",
      "secondary",
      "secondary-foreground",
      "accent",
      "accent-foreground",
      "success",
      "success-soft",
      "warning",
      "warning-soft",
      "danger",
      "danger-soft",
      "info",
      "info-soft",
      "me",
      "me-soft",
      "them",
      "them-soft",
      "muted",
      "recording",
    ];
    const missing: { block: string; name: string }[] = [];
    for (const block of [lightBlock, darkBlock]) {
      for (const name of required) {
        if (!block.tokens.has(name)) missing.push({ block: block.label, name });
      }
    }
    expect(missing).toEqual([]);
  });
});

describe("raw hex / rgb scan — components and lib", () => {
  test("no raw hex literal or rgb/rgba call appears outside the explicit allowlist", () => {
    const files = _listSourceFiles(REPO_WEB_SRC);
    const violations: { file: string; line: number; text: string }[] = [];
    for (const abs of files) {
      const rel = path.relative(REPO_WEB_SRC, abs);
      if (ALLOWLIST_FILES.has(rel)) continue;
      const contents = readFileSync(abs, "utf-8");
      const lines = contents.split("\n");
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i] ?? "";
        if (HEX_RE.test(line) || RGB_RE.test(line)) {
          violations.push({ file: rel, line: i + 1, text: line.trim() });
        }
      }
    }
    expect(violations).toEqual([]);
  });

  test("allowlist entries each carry a `reason:` justification", () => {
    for (const entry of RAW_COLOR_ALLOWLIST) {
      expect(entry.reason.length).toBeGreaterThan(0);
      expect(entry.reason).toMatch(/.+/);
    }
  });
});
