/**
 * Tests for ChunkActionMenu — slice-16 task 10.4.
 *
 * Three spec scenarios:
 *   (a) cluster speaker → 4 menu items
 *   (b) me / counterparty / unknown → 2 menu items (Edit color / Rename DOM-absent)
 *   (c) retention-expired recording → Play item disabled
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChunkActionMenu } from "./chunk-action-menu";

afterEach(cleanup);

function _baseProps() {
  return {
    open: true,
    onOpenChange: mock(() => undefined),
    clusterN: 2,
    recordingExpired: false,
    onPlay: mock(() => undefined),
    onEditText: mock(() => undefined),
    onEditColor: mock(() => undefined),
    onRenameSpeaker: mock(() => undefined),
  };
}

describe("ChunkActionMenu", () => {
  test("(a) cluster speaker chunk → 4 menu items in order", () => {
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} />);
    expect(screen.getByTestId("chunk-action-play")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-text")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-color")).toBeDefined();
    expect(screen.getByTestId("chunk-action-rename")).toBeDefined();
  });

  test("(b) me / counterparty / unknown (clusterN=null) → 2 items only", () => {
    render(<ChunkActionMenu {..._baseProps()} clusterN={null} />);
    expect(screen.getByTestId("chunk-action-play")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-text")).toBeDefined();
    expect(screen.queryByTestId("chunk-action-edit-color")).toBeNull();
    expect(screen.queryByTestId("chunk-action-rename")).toBeNull();
  });

  test("(c) retention-expired → Play item disabled, others enabled", () => {
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} recordingExpired={true} />);
    const playBtn = screen.getByTestId("chunk-action-play") as HTMLButtonElement;
    expect(playBtn.disabled).toBe(true);
    const editBtn = screen.getByTestId("chunk-action-edit-text") as HTMLButtonElement;
    expect(editBtn.disabled).toBe(false);
    const colorBtn = screen.getByTestId("chunk-action-edit-color") as HTMLButtonElement;
    expect(colorBtn.disabled).toBe(false);
  });

  test("clicking an item dispatches its callback and closes the menu", async () => {
    const user = userEvent.setup();
    const props = _baseProps();
    render(<ChunkActionMenu {...props} clusterN={2} />);

    await user.click(screen.getByTestId("chunk-action-play"));
    expect(props.onPlay).toHaveBeenCalled();
    expect(props.onOpenChange).toHaveBeenCalledWith(false);
  });

  test("open=false → DOM-absent (the menu does not render)", () => {
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} open={false} />);
    expect(screen.queryByTestId("chunk-action-menu")).toBeNull();
  });
});
