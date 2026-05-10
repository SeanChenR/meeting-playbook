/**
 * CaptureIndicator — slice-07 dual-stream pills (one per stream).
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";

import { CaptureIndicator } from "./capture-indicator";

afterEach(cleanup);

describe("CaptureIndicator", () => {
  test("null streamStatus renders nothing (idle / not in_progress)", () => {
    render(
      <CaptureIndicator
        streamStatus={null}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    expect(screen.queryByTestId("capture-indicator-group")).toBeNull();
  });

  test("renders two pills, one per stream", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const pills = screen.getAllByTestId("capture-indicator");
    expect(pills).toHaveLength(2);
    expect(pills.map((p) => p.dataset.stream)).toEqual(["me", "counterparty"]);
  });

  test("silence on counterparty: only counterparty pill shows warning, me pill stays active", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "silence" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const pills = screen.getAllByTestId("capture-indicator");
    const me = pills.find((p) => p.dataset.stream === "me")!;
    const cp = pills.find((p) => p.dataset.stream === "counterparty")!;

    expect(me.dataset.state).toBe("active");
    expect(cp.dataset.state).toBe("silence");
    // Counterparty pill carries the destructive (warning) tone.
    expect(cp.className).toContain("bg-(--color-destructive)/10");
    // Me pill stays normal.
    expect(me.className).not.toContain("bg-(--color-destructive)/10");
  });

  test("stopped renders grey pill with stream-stopped copy", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "stopped" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const pills = screen.getAllByTestId("capture-indicator");
    const cp = pills.find((p) => p.dataset.stream === "counterparty")!;
    expect(cp.dataset.state).toBe("stopped");
    expect(cp.className).toContain("bg-(--color-muted)");
    // Localized copy includes the counterparty display name.
    expect(cp.textContent).toContain("林經理");
  });

  test("ending=true overrides every pill to muted 'ending' look", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "silence" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
        ending
      />,
    );
    const pills = screen.getAllByTestId("capture-indicator");
    for (const pill of pills) {
      expect(pill.dataset.state).toBe("ending");
      expect(pill.className).toContain("bg-(--color-muted)");
    }
  });
});
