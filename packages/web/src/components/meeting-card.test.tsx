/**
 * MeetingCard tests — slice-15 task 8.4.
 *
 * Covers the new `showUploadShortcut` prop:
 *   (a) showUploadShortcut={true}  → renders hover-only shortcut button
 *   (b) showUploadShortcut omitted → no shortcut button in DOM
 *   (c) click on shortcut          → router history reflects ?action=upload,
 *                                    primary card link NOT followed
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MeetingCard } from "./meeting-card";
import type { Meeting } from "../lib/meetings-api";
import { renderWithRouter } from "../test/fixtures/router";

// refactor-meeting-detail-three-column: other test files (hover-glow-card,
// spicy-reveal, …) stub window.matchMedia to return reduced=true and don't
// restore it — when this file runs after them in the full suite, framer-motion
// reads the stale reduced=true and strips hover classes. Reset before each
// test here so this file is order-independent.
beforeEach(() => {
  // @ts-expect-error — stubbing for test isolation
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(cleanup);

function _meeting(overrides: Partial<Meeting> = {}): Meeting {
  return {
    id: "m_needs",
    user_id: "u",
    title: "Q3 follow-up",
    counterparty_display_name: "林經理",
    me_display_name: "Sean",
    status: "scheduled",
    asr_provider: "whisper",
    calendar_event_id: null,
    created_at: "2026-05-01T00:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: "2026-05-10T14:00:00Z",
    scheduled_end_at: null,
    ...overrides,
  };
}

describe("MeetingCard upload shortcut (slice-15 task 8.4)", () => {
  test("(a) renders hover-only shortcut when showUploadShortcut={true}", async () => {
    await renderWithRouter(<MeetingCard meeting={_meeting()} showUploadShortcut={true} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const shortcut = screen.getByTestId("meeting-card-upload-shortcut");
    expect(shortcut).toBeDefined();
    // The shortcut starts hidden (opacity-0) and fades in on group-hover.
    expect(shortcut.className).toContain("opacity-0");
    expect(shortcut.className).toContain("group-hover:opacity-100");
  });

  test("(b) omits shortcut DOM when showUploadShortcut not passed", async () => {
    await renderWithRouter(<MeetingCard meeting={_meeting()} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    expect(screen.queryByTestId("meeting-card-upload-shortcut")).toBeNull();
  });

  // ─── ui-overhaul-animated-surfaces task 6.2 ─────────────────────
  test("card link is wrapped by HoverGlowCard (lift + border glow)", async () => {
    await renderWithRouter(<MeetingCard meeting={_meeting()} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const cardLink = screen.getByTestId("meeting-card");
    expect(cardLink.getAttribute("data-hover-glow-card")).toBe("true");
    expect(cardLink.className).toContain("hover:-translate-y-1");
    expect(cardLink.className).toContain("hover:border-(--color-primary)");
  });

  test("tag-picker shortcut stays visible alongside HoverGlowCard wrapper", async () => {
    await renderWithRouter(<MeetingCard meeting={_meeting()} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    expect(screen.getByTestId("meeting-card-tag-shortcut")).toBeDefined();
  });

  test("(c) click on shortcut navigates with ?action=upload", async () => {
    const user = userEvent.setup();
    // The synthetic router only mounts a wildcard `/meetings/*`-style stub
    // so the typed navigate({to: "/meetings/$id"}) can resolve in memory
    // history without the real detail route tree.
    const { router } = await renderWithRouter(
      <MeetingCard meeting={_meeting()} showUploadShortcut={true} />,
      {
        initialEntries: ["/meetings/m_needs"],
        path: "/meetings/$id",
      },
    );

    const cardLink = screen.getByTestId("meeting-card");
    // Card link href stays plain (no action query). Click on the shortcut
    // must add the query without falling through to the link.
    expect(cardLink.getAttribute("href")).toBe("/meetings/m_needs");

    await user.click(screen.getByTestId("meeting-card-upload-shortcut"));

    // After the click, memory history should reflect the navigate({...})
    // call from the shortcut button. The exact href shape is
    // `/meetings/m_needs?action=upload`.
    await waitFor(() => {
      expect(router.history.location.pathname).toBe("/meetings/m_needs");
      expect(router.history.location.search).toContain("action=upload");
    });
  });
});
