/**
 * HeadphonesHint — slice-7 round-2 informational callout.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { HeadphonesHint } from "./headphones-hint";

afterEach(cleanup);

describe("HeadphonesHint", () => {
  test("renders the localized hint when visible=true", () => {
    render(<HeadphonesHint visible />);
    const el = screen.getByTestId("headphones-hint");
    expect(el).toBeDefined();
    // zh-TW (default) — body text comes from meetings.session.headphonesHint
    expect(el.textContent).toContain("耳機");
  });

  test("returns null when visible=false (no DOM node)", () => {
    render(<HeadphonesHint visible={false} />);
    expect(screen.queryByTestId("headphones-hint")).toBeNull();
  });
});
