/**
 * Tests for ChunkActionMenu — slice-16 task 10.4 (UI overhaul rewrite).
 *
 * Now owns its own ✎ trigger + animate-ui Popover wrapper, so tests
 * click the trigger to open the menu before asserting item presence.
 *
 *   (a) cluster speaker → 4 menu items
 *   (b) me / counterparty / unknown → 2 menu items (Edit color / Rename DOM-absent)
 *   (c) retention-expired recording → Play item disabled
 *   (d) clicking an item dispatches its callback
 *   (e) closed by default → menu DOM-absent until trigger clicked
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChunkActionMenu } from "./chunk-action-menu";

afterEach(cleanup);

function _baseProps() {
  return {
    clusterN: 2 as number | null,
    recordingExpired: false,
    onPlay: mock(() => undefined),
    onEditText: mock(() => undefined),
    onEditColor: mock(() => undefined),
    onRenameSpeaker: mock(() => undefined),
  };
}

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTestId("chunk-action-menu-trigger"));
}

describe("ChunkActionMenu", () => {
  test("(a) cluster speaker chunk → 4 menu items in order", async () => {
    const user = userEvent.setup();
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} />);
    await openMenu(user);
    expect(screen.getByTestId("chunk-action-play")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-text")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-color")).toBeDefined();
    expect(screen.getByTestId("chunk-action-rename")).toBeDefined();
  });

  test("(b) me / counterparty / unknown (clusterN=null) → 2 items only", async () => {
    const user = userEvent.setup();
    render(<ChunkActionMenu {..._baseProps()} clusterN={null} />);
    await openMenu(user);
    expect(screen.getByTestId("chunk-action-play")).toBeDefined();
    expect(screen.getByTestId("chunk-action-edit-text")).toBeDefined();
    expect(screen.queryByTestId("chunk-action-edit-color")).toBeNull();
    expect(screen.queryByTestId("chunk-action-rename")).toBeNull();
  });

  test("(c) retention-expired → Play item disabled, others enabled", async () => {
    const user = userEvent.setup();
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} recordingExpired={true} />);
    await openMenu(user);
    const playBtn = screen.getByTestId("chunk-action-play") as HTMLButtonElement;
    expect(playBtn.disabled).toBe(true);
    const editBtn = screen.getByTestId("chunk-action-edit-text") as HTMLButtonElement;
    expect(editBtn.disabled).toBe(false);
    const colorBtn = screen.getByTestId("chunk-action-edit-color") as HTMLButtonElement;
    expect(colorBtn.disabled).toBe(false);
  });

  test("(d) clicking an item dispatches its callback", async () => {
    const user = userEvent.setup();
    const props = _baseProps();
    render(<ChunkActionMenu {...props} clusterN={2} />);
    await openMenu(user);
    await user.click(screen.getByTestId("chunk-action-play"));
    expect(props.onPlay).toHaveBeenCalled();
  });

  test("(e) menu is DOM-absent before the trigger is clicked", () => {
    render(<ChunkActionMenu {..._baseProps()} clusterN={2} />);
    expect(screen.queryByTestId("chunk-action-menu")).toBeNull();
  });
});
