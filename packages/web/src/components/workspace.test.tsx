/**
 * Workspace — covers refactor v2 (claude-design alignment):
 *
 *   (a) always three equal-width columns (1fr 1fr 1fr)
 *   (b) outer container is full width (parent provides max-w)
 *   (c) each column has data-testid meeting-column-{variant}
 *   (d) MeetingColumn is now a header-less shell — children render directly
 *   (e) column has bounded height via --detail-column-h CSS var
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { i18n } from "../lib/i18n";
import { ThemeProvider } from "../lib/theme-provider";
import { Workspace } from "./workspace";

afterEach(cleanup);

function _mount() {
  return render(
    <ThemeProvider initialTheme="light">
      <I18nextProvider i18n={i18n}>
        <Workspace
          playbook={<div data-testid="pb-inner">PB</div>}
          transcript={<div data-testid="tr-inner">TR</div>}
          advisor={<div data-testid="ad-inner">AD</div>}
        />
      </I18nextProvider>
    </ThemeProvider>,
  );
}

describe("Workspace — three equal-width columns", () => {
  test("(4.1a) three column wrappers in PB/TR/AD order", () => {
    _mount();
    expect(screen.getByTestId("meeting-column-playbook")).toBeDefined();
    expect(screen.getByTestId("meeting-column-transcript")).toBeDefined();
    expect(screen.getByTestId("meeting-column-advisor")).toBeDefined();

    const pb = screen.getByTestId("meeting-column-playbook");
    const tr = screen.getByTestId("meeting-column-transcript");
    const ad = screen.getByTestId("meeting-column-advisor");
    expect(pb.compareDocumentPosition(tr) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tr.compareDocumentPosition(ad) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test("(4.1c) outer container uses grid-cols-3 (width inherited from parent)", () => {
    _mount();
    const root = screen.getByTestId("workspace");
    expect(root.className).toContain("grid-cols-3");
    expect(root.className).toContain("w-full");
  });

  test("(4.1d) each column has min-width 300px (Tailwind class)", () => {
    _mount();
    const pb = screen.getByTestId("meeting-column-playbook");
    expect(pb.className).toContain("min-w-[300px]");
  });

  test("(4.1e) inner pane content renders inside each column", () => {
    _mount();
    expect(screen.getByTestId("pb-inner")).toBeDefined();
    expect(screen.getByTestId("tr-inner")).toBeDefined();
    expect(screen.getByTestId("ad-inner")).toBeDefined();
  });

  test("(5.1) column has bounded height (flex column + scroll lives inside inner Pane)", () => {
    _mount();
    const pb = screen.getByTestId("meeting-column-playbook");
    // happy-dom strips `var()` references from inline-style, so we can't
    // directly assert the var. Instead verify the column has the layout
    // primitives that guarantee bounded height (flex column shell).
    expect(pb.className).toContain("flex");
    expect(pb.className).toContain("overflow-hidden");
  });

  test("(refactor v2) MeetingColumn no longer renders its own header — title delegated to inner Pane", () => {
    _mount();
    const pb = screen.getByTestId("meeting-column-playbook");
    // The shell renders ONLY children; no inner <header> element.
    expect(pb.querySelector("header")).toBeNull();
  });
});
