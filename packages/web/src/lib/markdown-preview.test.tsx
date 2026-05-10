/**
 * MarkdownPreview — slice-7 round-2 read-only markdown renderer.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { MarkdownPreview } from "./markdown-preview";

afterEach(cleanup);

describe("MarkdownPreview", () => {
  test("renders heading + ordered/unordered lists + strong text from markdown source", () => {
    const source = "# Goals\n\n- A\n- **B**";
    render(<MarkdownPreview source={source} />);
    const wrapper = screen.getByTestId("markdown-preview");
    expect(wrapper.querySelector("h1")?.textContent).toBe("Goals");
    const lis = wrapper.querySelectorAll("li");
    expect(lis.length).toBe(2);
    // Bold rendered as <strong>
    expect(wrapper.querySelector("strong")?.textContent).toBe("B");
  });

  test("renders GFM tables via remark-gfm", () => {
    const source = "| col1 | col2 |\n|------|------|\n| a | b |";
    render(<MarkdownPreview source={source} />);
    const wrapper = screen.getByTestId("markdown-preview");
    expect(wrapper.querySelector("table")).not.toBeNull();
    const cells = wrapper.querySelectorAll("td");
    expect(cells.length).toBe(2);
  });

  test("rehype-sanitize strips script tags from the rendered output", () => {
    // Markdown allows inline raw HTML; without sanitisation a `<script>`
    // payload would render. With rehype-sanitize the script element MUST
    // be removed from the rendered DOM.
    const source = "Hello world\n\n<script>alert('xss')</script>";
    render(<MarkdownPreview source={source} />);
    const wrapper = screen.getByTestId("markdown-preview");
    expect(wrapper.querySelector("script")).toBeNull();
    expect(wrapper.textContent).toContain("Hello world");
  });

  test("empty source renders an empty wrapper (does not crash)", () => {
    render(<MarkdownPreview source="" />);
    expect(screen.getByTestId("markdown-preview")).toBeDefined();
  });
});
