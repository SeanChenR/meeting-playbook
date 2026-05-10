/**
 * LayoutSwitcher — slice-07 controlled toggle.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { LayoutSwitcher } from "./layout-switcher";

afterEach(cleanup);

describe("LayoutSwitcher", () => {
  test("renders two buttons with localized aria labels", () => {
    render(<LayoutSwitcher layout="columns" onChange={() => {}} />);
    const stack = screen.getByTestId("layout-switcher-stack");
    const cols = screen.getByTestId("layout-switcher-columns");
    expect(stack.getAttribute("aria-label")).toBeTruthy();
    expect(cols.getAttribute("aria-label")).toBeTruthy();
  });

  test("active button reflects current layout via aria-pressed", () => {
    render(<LayoutSwitcher layout="stack" onChange={() => {}} />);
    expect(screen.getByTestId("layout-switcher-stack").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("layout-switcher-columns").getAttribute("aria-pressed")).toBe(
      "false",
    );
  });

  test("clicking a button calls onChange with the corresponding layout value", () => {
    const onChange = mock(() => {});
    render(<LayoutSwitcher layout="columns" onChange={onChange} />);

    fireEvent.click(screen.getByTestId("layout-switcher-stack"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("stack");

    fireEvent.click(screen.getByTestId("layout-switcher-columns"));
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith("columns");
  });
});
