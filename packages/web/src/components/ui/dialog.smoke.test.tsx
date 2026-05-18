/**
 * Dialog smoke tests — ui-overhaul-primitive-upgrade task 2.
 *
 * Behaviour contract: Dialog SHALL render with backdrop blur and use the
 * Aura `--color-surface` token. Reduced-motion users get instant variants
 * (motion library handles that via `useReducedMotion`).
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./dialog";

afterEach(cleanup);

describe("Dialog (animate-ui motion)", () => {
  test("renders role=dialog with title + description aria-wiring", () => {
    render(
      <Dialog open onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hello</DialogTitle>
            <DialogDescription>World</DialogDescription>
          </DialogHeader>
          <p>Body</p>
        </DialogContent>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Hello")).toBeDefined();
    expect(screen.getByText("World")).toBeDefined();
  });

  test("backdrop element has blur class and surface token usage", () => {
    render(
      <Dialog open onOpenChange={() => {}}>
        <DialogContent data-testid="dialog-content">
          <DialogHeader>
            <DialogTitle>T</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>,
    );

    const content = screen.getByTestId("dialog-content");
    expect(content.className).toContain("bg-(--color-surface)");

    // backdrop is the parent of content with backdrop-blur in its class list
    const backdrop = content.parentElement;
    expect(backdrop).toBeTruthy();
    expect(backdrop?.className).toContain("backdrop-blur");
  });

  test("hidden when open=false", () => {
    render(
      <Dialog open={false} onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>T</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>,
    );

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
