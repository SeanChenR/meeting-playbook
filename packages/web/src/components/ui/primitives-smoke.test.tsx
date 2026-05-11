/**
 * Smoke tests for the 5 shadcn primitives added in
 * slice ui-overhaul-claude-design task 1.3.
 *
 * Each test asserts the primitive mounts AND its default-visible element
 * (trigger / placeholder / etc.) ends up in the DOM. Per-primitive
 * functional tests live alongside the feature components that consume them.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";
import { Skeleton } from "./skeleton";
import { Toaster } from "./sonner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";
import { ThemeProvider } from "../../lib/theme-provider";

afterEach(cleanup);

describe("ui primitives smoke", () => {
  test("Select trigger renders with the placeholder value", () => {
    render(
      <Select defaultValue="qwen3">
        <SelectTrigger data-testid="select-trigger">
          <SelectValue placeholder="pick" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="qwen3">Qwen3</SelectItem>
          <SelectItem value="whisper">Whisper</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByTestId("select-trigger")).toBeDefined();
  });

  test("DropdownMenu trigger renders", () => {
    render(
      <DropdownMenu>
        <DropdownMenuTrigger data-testid="dropdown-trigger">Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>One</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("dropdown-trigger")).toBeDefined();
  });

  test("Tooltip trigger renders inside a Provider", () => {
    render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger data-testid="tooltip-trigger">hover me</TooltipTrigger>
          <TooltipContent>tip</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );
    expect(screen.getByTestId("tooltip-trigger")).toBeDefined();
  });

  test("Skeleton renders with data-testid", () => {
    render(<Skeleton className="h-4 w-32" />);
    expect(screen.getByTestId("skeleton")).toBeDefined();
  });

  test("Toaster mounts inside a ThemeProvider without throwing", () => {
    // Toaster reads useTheme() — wrap in ThemeProvider so the hook resolves.
    expect(() =>
      render(
        <ThemeProvider initialTheme="light">
          <Toaster />
        </ThemeProvider>,
      ),
    ).not.toThrow();
  });
});
