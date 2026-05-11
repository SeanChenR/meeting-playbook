/**
 * Workspace tests — slice ui-overhaul-claude-design task 5.5.
 *
 * Covers:
 *   (a) `columns` layout sets a 3-column grid template
 *   (b) `stack` layout sets a 3-row grid template
 *   (c) `prefers-reduced-motion: reduce` is respected (sanity: component
 *       still mounts and renders all three panes — framer-motion uses
 *       `transition={{ duration: 0 }}` for instant layout under reduced motion)
 *   (d) All three pane testids are present
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { Workspace } from "./workspace";

function _stubMatchMedia(reduced: boolean) {
  // @ts-expect-error — overriding for tests
  window.matchMedia = (q: string) => ({
    matches: q.includes("reduce") ? reduced : false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
}

beforeEach(() => {
  _stubMatchMedia(false);
});

afterEach(cleanup);

describe("Workspace layout", () => {
  test("(a) columns mode sets a 3-column grid template", () => {
    render(
      <Workspace
        layout="columns"
        playbook={<div data-testid="pb" />}
        transcript={<div data-testid="tr" />}
        advisor={<div data-testid="ad" />}
      />,
    );
    const root = screen.getByTestId("workspace");
    const tmpl = root.style.gridTemplateColumns;
    // Three column tracks separated by spaces.
    expect(tmpl.split(/\s+(?![^(]*\))/).filter(Boolean).length).toBe(3);
    expect(tmpl).toContain("260px");
    expect(tmpl).toContain("360px");
  });

  test("(b) stack mode sets a 3-row grid template", () => {
    render(<Workspace layout="stack" playbook={<div />} transcript={<div />} advisor={<div />} />);
    const root = screen.getByTestId("workspace");
    const tmpl = root.style.gridTemplateRows;
    expect(tmpl.split(/\s+(?![^(]*\))/).filter(Boolean).length).toBe(3);
    expect(tmpl).toContain("180px");
    expect(tmpl).toContain("220px");
  });

  test("(c) prefers-reduced-motion=reduce still mounts the workspace", () => {
    _stubMatchMedia(true);
    expect(() =>
      render(
        <Workspace
          layout="columns"
          playbook={<div data-testid="pb" />}
          transcript={<div data-testid="tr" />}
          advisor={<div data-testid="ad" />}
        />,
      ),
    ).not.toThrow();
    // The three panes still mount; framer-motion just uses a 0-duration transition.
    expect(screen.getByTestId("workspace-pane-playbook")).toBeDefined();
    expect(screen.getByTestId("workspace-pane-transcript")).toBeDefined();
    expect(screen.getByTestId("workspace-pane-advisor")).toBeDefined();
  });

  test("(d) renders all three pane slots", () => {
    render(
      <Workspace
        layout="columns"
        playbook={<div data-testid="pb" />}
        transcript={<div data-testid="tr" />}
        advisor={<div data-testid="ad" />}
      />,
    );
    expect(screen.getByTestId("pb")).toBeDefined();
    expect(screen.getByTestId("tr")).toBeDefined();
    expect(screen.getByTestId("ad")).toBeDefined();
  });
});
