/**
 * LayoutSwitcher tests — slice ui-overhaul-claude-design task 5.4.
 *
 * Original slice-07 assertions:
 *   - Two buttons render with localised aria-labels
 *   - aria-pressed reflects current layout
 *   - Clicking calls onChange with the new layout value
 *
 * Phase-5 additions per task contract:
 *   (a) Renders 2 icon-only buttons inside a segmented container
 *   (b) Clicking rows writes localStorage + triggers onChange
 *   (c) On remount, the persisted layout value seeds the default state
 *       (exercises `useDetailLayout` end-to-end).
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen, renderHook, act } from "@testing-library/react";

import { LayoutSwitcher } from "./layout-switcher";
import { useDetailLayout } from "../hooks/use-detail-layout";

const STORAGE_KEY = "meeting-detail.layout";

beforeEach(() => {
  window.localStorage.removeItem(STORAGE_KEY);
});

afterEach(cleanup);

describe("LayoutSwitcher", () => {
  test("renders two icon-only buttons inside the segmented container", () => {
    render(<LayoutSwitcher layout="columns" onChange={() => {}} />);
    const root = screen.getByTestId("layout-switcher");
    const stack = screen.getByTestId("layout-switcher-stack");
    const cols = screen.getByTestId("layout-switcher-columns");
    expect(root.contains(stack)).toBe(true);
    expect(root.contains(cols)).toBe(true);
    // Icon-only: buttons should contain an <svg> from lucide.
    expect(stack.querySelector("svg")).not.toBeNull();
    expect(cols.querySelector("svg")).not.toBeNull();
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

  test("(b) clicking rows writes localStorage and updates the hook value", () => {
    function Harness() {
      const [layout, setLayout] = useDetailLayout();
      return <LayoutSwitcher layout={layout} onChange={setLayout} />;
    }
    render(<Harness />);

    fireEvent.click(screen.getByTestId("layout-switcher-stack"));
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("stack");
    expect(screen.getByTestId("layout-switcher-stack").getAttribute("aria-pressed")).toBe("true");
  });

  test("(c) useDetailLayout seeds default from localStorage on remount", () => {
    window.localStorage.setItem(STORAGE_KEY, "stack");
    const { result } = renderHook(() => useDetailLayout());
    // useEffect re-reads stored value after mount; flush.
    act(() => undefined);
    expect(result.current[0]).toBe("stack");
  });
});
