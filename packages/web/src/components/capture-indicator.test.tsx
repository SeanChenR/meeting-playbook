/**
 * CaptureIndicator tests — ui-overhaul-animated-surfaces task 3.2 + 3.3.
 *
 * The component now emits exactly one of four discrete `data-state` values
 * per stream — `connecting | listening | speaking | off` — driven by:
 *
 *   - `streamStatus[s]` (`active` / `silence` / `stopped`)
 *   - `ending` flag (forces `off`)
 *   - `lastChunkAt[s]` (most recent transcript_chunk timestamp per stream)
 *   - `streamStartedAt[s]` (first time the stream was observed active)
 *
 * State derivation (from spec table):
 *   active + no chunk within first 8s        → connecting
 *   active + recent chunk (≤2s)              → speaking
 *   active otherwise                         → listening
 *   silence                                  → listening
 *   stopped OR ending                        → off
 *
 * Structural contract:
 *   - 1 row per stream (`me`, `counterparty`)
 *   - `data-testid="capture-indicator"` per row
 *   - `data-stream` ∈ {`me`,`counterparty`}, `data-state` ∈ {`connecting`,`listening`,`speaking`,`off`}
 *   - 10 bars per row (`data-testid="bar-visualizer-bar"`)
 *   - Visible label resolves from `meetings.session.barVisualizer.<state>`
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, render, screen, within } from "@testing-library/react";

import { CaptureIndicator } from "./capture-indicator";

beforeEach(() => {
  // @ts-expect-error happy-dom override
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(cleanup);

const NOW = new Date("2026-05-18T12:00:00Z").getTime();

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

  test("active streams with no chunks yet within 8s → both rows connecting", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 3_000, counterparty: NOW - 3_000 }}
        lastChunkAt={{ me: null, counterparty: null }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    expect(rows).toHaveLength(2);
    for (const row of rows) {
      expect(row.dataset.state).toBe("connecting");
    }
    // Visible label resolves to barVisualizer.connecting (zh-TW default)
    expect(screen.getAllByText("連接中…").length).toBeGreaterThanOrEqual(1);
  });

  test("active stream past 8s with no chunks → listening", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 12_000, counterparty: NOW - 12_000 }}
        lastChunkAt={{ me: null, counterparty: null }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("listening");
    }
  });

  test("active stream with recent chunk (≤2s) → speaking", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 500, counterparty: NOW - 500 }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("speaking");
    }
  });

  test("active stream with stale chunk (>2s) → listening", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 5_000, counterparty: NOW - 5_000 }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("listening");
    }
  });

  test("silence → listening", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "silence", counterparty: "silence" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("listening");
    }
  });

  test("stopped → off", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "stopped", counterparty: "stopped" }}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("off");
    }
  });

  test("ending=true forces off on every row", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 100, counterparty: NOW - 100 }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
        ending
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(row.dataset.state).toBe("off");
    }
  });

  test("mixed: me active+recent chunk speaking, counterparty silence listening", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "silence" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 800, counterparty: null }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    const me = rows.find((r) => r.dataset.stream === "me")!;
    const cp = rows.find((r) => r.dataset.stream === "counterparty")!;
    expect(me.dataset.state).toBe("speaking");
    expect(cp.dataset.state).toBe("listening");
  });

  test("each row renders 10 visualizer bars", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 500, counterparty: NOW - 500 }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    for (const row of screen.getAllByTestId("capture-indicator")) {
      expect(within(row).getAllByTestId("bar-visualizer-bar")).toHaveLength(10);
    }
  });

  test("me row uses --color-me tone, counterparty uses --color-them", () => {
    render(
      <CaptureIndicator
        streamStatus={{ me: "active", counterparty: "active" }}
        streamStartedAt={{ me: NOW - 30_000, counterparty: NOW - 30_000 }}
        lastChunkAt={{ me: NOW - 500, counterparty: NOW - 500 }}
        nowMs={NOW}
        meDisplayName="Sean"
        counterpartyDisplayName="林經理"
      />,
    );
    const rows = screen.getAllByTestId("capture-indicator");
    const me = rows.find((r) => r.dataset.stream === "me")!;
    const cp = rows.find((r) => r.dataset.stream === "counterparty")!;
    const meBar = within(me).getAllByTestId("bar-visualizer-bar")[0]!;
    const cpBar = within(cp).getAllByTestId("bar-visualizer-bar")[0]!;
    expect(meBar.style.background).toContain("var(--color-me)");
    expect(cpBar.style.background).toContain("var(--color-them)");
  });
});
