/**
 * TagChip tests — slice-17 task 5.2.
 *
 * Verifies:
 *   (a) light background → dark-text variant class is applied
 *   (b) dark background  → light-text variant class is applied
 *   (c) onRemove callback fires when the close button is clicked
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TagChip } from "./tag-chip";

afterEach(cleanup);

describe("TagChip", () => {
  test("light background renders the dark-text variant", () => {
    render(<TagChip name="客戶X" color="#FEF3C7" />);
    const chip = screen.getByTestId("tag-chip");
    expect(chip.getAttribute("data-text-variant")).toBe("dark");
  });

  test("dark background renders the light-text variant", () => {
    render(<TagChip name="面試" color="#7C2D12" />);
    const chip = screen.getByTestId("tag-chip");
    expect(chip.getAttribute("data-text-variant")).toBe("light");
  });

  test("clicking the remove button fires onRemove", async () => {
    const calls: string[] = [];
    const user = userEvent.setup();
    render(<TagChip name="客戶X" color="#DDD6FE" onRemove={() => calls.push("x")} />);
    const button = screen.getByTestId("tag-chip-remove");
    await user.click(button);
    expect(calls).toEqual(["x"]);
  });
});
