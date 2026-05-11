/**
 * CaptureIndicator tests — slice ui-overhaul-claude-design task 5.3.
 *
 * The bar-sparkline rewrite replaces the slice-7 pill design, so the
 * structural contract changes:
 *   - One row per stream (`me` + `counterparty`), `data-stream` set
 *   - Each row contains 10 sparkline bars
 *   - `recording=false` (status `stopped` or `ending=true`) collapses
 *     the dot to muted foreground colour and shrinks bars to 1px.
 *   - `streamStatus === null` still renders nothing (idle / not in_progress)
 *   - `ending=true` overrides every row to a muted state
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen, within } from "@testing-library/react";

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

  test("(a) recording=true renders 2 rows, one per stream", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    expect(rows).toHaveLength(2);
    expect(rows.map((r) => r.dataset.stream)).toEqual(["me", "counterparty"]);
  });

  test("(b) each row contains 10 sparkline bars", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    for (const row of rows) {
      const bars = within(row).getAllByTestId("capture-indicator-bar");
      expect(bars).toHaveLength(10);
    }
  });

  test("(c) recording=false (stopped) — dot uses muted token and bars shrink to 1px", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "stopped", counterparty: "stopped" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    for (const row of rows) {
      expect(row.dataset.state).toBe("stopped");
      const dot = row.querySelector("span[aria-hidden]");
      expect(dot?.className ?? "").toContain("bg-(--color-muted-foreground)");
      const bars = within(row).getAllByTestId("capture-indicator-bar");
      for (const bar of bars) {
        expect((bar as HTMLElement).style.height).toBe("1px");
      }
    }
  });

  test("silence on counterparty: only counterparty row marked silence; me row stays active", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "silence" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    const me = rows.find((r) => r.dataset.stream === "me")!;
    const cp = rows.find((r) => r.dataset.stream === "counterparty")!;
    expect(me.dataset.state).toBe("active");
    expect(cp.dataset.state).toBe("silence");
  });

  test("ending=true overrides every row to a muted 'ending' look", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
        ending
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    for (const row of rows) {
      expect(row.dataset.state).toBe("ending");
      const bars = within(row).getAllByTestId("capture-indicator-bar");
      for (const bar of bars) {
        expect((bar as HTMLElement).style.height).toBe("1px");
      }
    }
  });
});
