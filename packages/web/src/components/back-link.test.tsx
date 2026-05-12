/**
 * BackLink tests — slice ui-overhaul-claude-design task 2.4.
 *
 * Covers:
 *   - Renders the ArrowLeft icon + default fallback text from i18n
 *   - Click invokes router navigation (verified by mocking Link)
 *   - Custom labelKey overrides the default text
 */

import { afterEach, beforeAll, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";

const navigateSpy = mock(() => undefined);

beforeAll(() => {
  mock.module("@tanstack/react-router", () => ({
    Link: ({
      to,
      search,
      params: _params,
      children,
      ...rest
    }: {
      to: string;
      search?: Record<string, string>;
      params?: unknown;
      children: ReactNode;
      [k: string]: unknown;
    }) => {
      // Serialize the optional `search` prop into the href so leaked
      // mock instances don't drop query-driven behaviour in route tests
      // (e.g. /meetings/new?from=calendar).
      const path = typeof to === "string" ? to : "#";
      const qs =
        search && typeof search === "object"
          ? new URLSearchParams(search as Record<string, string>).toString()
          : "";
      const href = qs ? `${path}?${qs}` : path;
      return (
        <a
          href={href}
          onClick={(e) => {
            e.preventDefault();
            navigateSpy();
          }}
          {...rest}
        >
          {children}
        </a>
      );
    },
  }));
});

afterEach(cleanup);

const { BackLink } = await import("./back-link");

describe("BackLink", () => {
  test("renders the ArrowLeft icon and default 返回列表 label", () => {
    render(<BackLink to="/meetings" />);
    const link = screen.getByTestId("back-link");
    expect(link).toBeDefined();
    // lucide-react renders icons as <svg>; assert at least one SVG child.
    expect(link.querySelector("svg")).not.toBeNull();
    // Default labelKey resolves to "返回列表" (zh-TW) or "Back to list" (en).
    expect(link.textContent).toMatch(/(返回列表|Back to list)/);
  });

  test("uses a custom labelKey when provided (nav.back)", () => {
    render(<BackLink to="/meetings" labelKey="nav.back" />);
    expect(screen.getByTestId("back-link").textContent).toMatch(/(^返回$|^Back$)/);
  });

  test("clicking the link triggers router navigation", async () => {
    const user = userEvent.setup();
    const before = navigateSpy.mock.calls.length;
    render(<BackLink to="/meetings" />);
    await user.click(screen.getByTestId("back-link"));
    expect(navigateSpy.mock.calls.length).toBeGreaterThan(before);
  });
});
