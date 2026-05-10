/**
 * markdown-export — slice-10 helper tests.
 *
 * Covers the filename builder (non-filesystem-safe char stripping) and
 * the blob fallback path (when File System Access API is unavailable).
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { buildExportFilename, exportSummaryAsMarkdown } from "./markdown-export";

const _MEETING = { title: "Q3/Q4 review: 對方?", created_at: "2026-05-11T01:30:00Z" };

describe("buildExportFilename", () => {
  test("strips path separators and Windows reserved chars; keeps Chinese", () => {
    const fn = buildExportFilename(_MEETING);
    expect(fn).toMatch(/^Q3_Q4 review_ 對方_-2026-05-11\.md$/);
  });

  test("uses the YYYY-MM-DD slice of created_at", () => {
    expect(buildExportFilename({ title: "x", created_at: "2026-01-15T23:59:59Z" })).toBe(
      "x-2026-01-15.md",
    );
  });
});

describe("exportSummaryAsMarkdown — blob fallback", () => {
  let originalSavePicker: unknown;
  let originalCreateObjectURL: unknown;
  let originalRevokeObjectURL: unknown;

  beforeEach(() => {
    originalSavePicker = (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker;
    originalCreateObjectURL = URL.createObjectURL;
    originalRevokeObjectURL = URL.revokeObjectURL;
    // Force the fallback path.
    delete (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker;
    URL.createObjectURL = mock(() => "blob:mocked-url") as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = mock(() => {}) as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    if (originalSavePicker !== undefined) {
      (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker =
        originalSavePicker;
    }
    URL.createObjectURL = originalCreateObjectURL as typeof URL.createObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL as typeof URL.revokeObjectURL;
  });

  test("creates blob, anchor click, then revokes URL when File System Access API unavailable", async () => {
    let clickCalled = false;
    const origCreate = document.createElement.bind(document);
    document.createElement = ((tag: string) => {
      const el = origCreate(tag);
      if (tag === "a") {
        const a = el as HTMLAnchorElement;
        const origClick = a.click.bind(a);
        a.click = () => {
          clickCalled = true;
          // don't actually navigate
          origClick();
        };
      }
      return el;
    }) as typeof document.createElement;
    try {
      await exportSummaryAsMarkdown(_MEETING, "## 重點討論\n- foo\n");
      expect(clickCalled).toBe(true);
      expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
      expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    } finally {
      document.createElement = origCreate as typeof document.createElement;
    }
  });
});
