/**
 * RecordingModeSelector — slice-27 task 5.1.
 *
 * Spec ADDED requirement "Pre-flight recording mode selector chooses
 * dual-channel or single-channel capture" — render two mutually-exclusive
 * options, default `dual`, change-event propagation, disabled state. All
 * label text comes from `meetings.session.recordingMode.*` i18n keys.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RecordingModeSelector } from "./recording-mode-selector";

afterEach(cleanup);

describe("RecordingModeSelector", () => {
  test("renders two radios with the supplied value (default dual) selected", () => {
    render(<RecordingModeSelector value="dual" onChange={() => {}} />);
    const dual = screen.getByTestId("recording-mode-dual") as HTMLInputElement;
    const single = screen.getByTestId("recording-mode-single") as HTMLInputElement;
    expect(dual.type).toBe("radio");
    expect(single.type).toBe("radio");
    expect(dual.checked).toBe(true);
    expect(single.checked).toBe(false);
  });

  test("renders the supplied value=single as the selected option", () => {
    render(<RecordingModeSelector value="single" onChange={() => {}} />);
    const dual = screen.getByTestId("recording-mode-dual") as HTMLInputElement;
    const single = screen.getByTestId("recording-mode-single") as HTMLInputElement;
    expect(dual.checked).toBe(false);
    expect(single.checked).toBe(true);
  });

  test("onChange fires with the new mode when the user picks single", async () => {
    const user = userEvent.setup();
    const changes: string[] = [];
    render(
      <RecordingModeSelector
        value="dual"
        onChange={(m) => {
          changes.push(m);
        }}
      />,
    );
    await user.click(screen.getByTestId("recording-mode-single"));
    expect(changes).toContain("single");
  });

  test("disabled prop makes both radios non-interactive", async () => {
    const user = userEvent.setup();
    const changes: string[] = [];
    render(
      <RecordingModeSelector
        value="dual"
        disabled
        onChange={(m) => {
          changes.push(m);
        }}
      />,
    );
    const single = screen.getByTestId("recording-mode-single") as HTMLInputElement;
    expect(single.disabled).toBe(true);
    await user.click(single);
    expect(changes).toEqual([]);
  });

  test("helper texts come from the i18n keys (zh-TW default)", () => {
    render(<RecordingModeSelector value="dual" onChange={() => {}} />);
    // zh-TW: dualHelper = "需要 BlackHole 路由系統聲音"; singleHelper contains "對方".
    expect(screen.getByTestId("recording-mode-dual-helper").textContent).toContain("BlackHole");
    expect(screen.getByTestId("recording-mode-single-helper").textContent).toContain("對方");
  });
});
