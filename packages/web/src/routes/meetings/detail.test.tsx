import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "../../lib/theme-provider";

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: { user: { name: "Sean", email: "sean@example.com" } },
      isPending: false,
    }),
  },
}));

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
const originalFetch = globalThis.fetch;

import { MeetingDetail } from "./detail";

const SAMPLE_MEETING = {
  id: "m_abc",
  user_id: "u",
  title: "Q3 review",
  counterparty_display_name: "林經理",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: "2026-05-07T10:00:00Z",
  started_at: null,
  ended_at: null,
};

async function renderInRouter(initialEntry = "/meetings/m_abc") {
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => <MeetingDetail />,
  });
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <div data-testid="redirected-list">on list</div>,
  });
  const routeTree = rootRoute.addChildren([detailRoute, listRoute]);
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createRouter({ routeTree, history });
  await router.load();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return { router };
}

describe("MeetingDetail route", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders title, display names, status, and the embedded PlaybookPane", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response(
          JSON.stringify({
            id: "pb_abc",
            meeting_id: "m_abc",
            free_form_markdown: "",
            objective: "",
            counterparty_profile: "",
            anticipated_topics: "",
            anticipated_objections: "",
            talking_points: "",
            red_lines: "",
            created_at: "2026-05-07T10:00:00Z",
            updated_at: "2026-05-07T10:00:00Z",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    expect(screen.getByText(/林經理/)).toBeDefined();
    expect(screen.getByText(/Sean/)).toBeDefined();
    // zh-TW: meetings.status.scheduled → "已排程"
    expect(screen.getByText(/已排程/)).toBeDefined();

    // PlaybookPane is mounted: heading + freeform sub-toggle visible.
    // Slice-26 D1: mount default is Preview (not Edit) — assert via the
    // sub-toggle button instead of the now-absent textarea.
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /^Playbook$/ })).toBeDefined();
    });
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();
  });

  test("delete confirmation flow: open dialog → confirm → DELETE → redirect to list", async () => {
    const user = userEvent.setup();
    let deleted = false;
    fetchHandler = async (url, init) => {
      if (init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^刪除 Meeting$/ }));

    // Dialog open: title + confirm button visible.
    expect(screen.getByText(/確定要刪除這個 Meeting？/)).toBeDefined();
    await user.click(screen.getByRole("button", { name: /^確定刪除$/ }));

    await waitFor(() => {
      expect(screen.getByTestId("redirected-list")).toBeDefined();
    });
    expect(deleted).toBe(true);
  });

  test("delete dialog cancel keeps the meeting visible", async () => {
    const user = userEvent.setup();
    let deleted = false;
    fetchHandler = async (url, init) => {
      if (init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^刪除 Meeting$/ }));
    await user.click(screen.getByRole("button", { name: /^取消$/ }));

    // Cancel must close the dialog and NOT issue DELETE.
    expect(deleted).toBe(false);
    expect(screen.getByText("Q3 review")).toBeDefined();
  });

  // ─── Phase 5 additions ─────────────────────────────────────────────────

  test("(5.1) BackLink to /meetings renders at the top of the detail page", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    const back = screen.getByTestId("back-link");
    expect(back.getAttribute("href")).toBe("/meetings");
  });

  test("(5.1) LayoutSwitcher only renders on the workspace tab", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    // Workspace tab is the default; switcher slot is visible.
    expect(screen.queryByTestId("detail-layout-switcher-slot")).not.toBeNull();
    expect(screen.queryByTestId("layout-switcher")).not.toBeNull();
  });

  test("(5.2) MetadataCard renders with title + 3 metadata rows + selector + indicator slots", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByTestId("meeting-metadata-card")).toBeDefined();
    });
    // Left column: title + 3 metadata rows.
    expect(screen.getByTestId("meeting-title").textContent).toContain("Q3 review");
    expect(screen.getByTestId("meeting-row-counterparty")).toBeDefined();
    expect(screen.getByTestId("meeting-row-me")).toBeDefined();
    expect(screen.getByTestId("meeting-row-recording")).toBeDefined();
    // Right column: ASR selector mount (CaptureIndicator is hidden until session in_progress).
    expect(screen.getByTestId("asr-provider-selector")).toBeDefined();
  });

  test("(5.6) summary tab carries data-disabled when status !== completed", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    const summary = screen.getByTestId("detail-tab-summary");
    // Radix Tabs sets `data-disabled` on disabled triggers (and the native
    // `disabled` attribute on the button); accept either signal.
    const isDisabled =
      summary.hasAttribute("data-disabled") || (summary as HTMLButtonElement).disabled === true;
    expect(isDisabled).toBe(true);
  });

  test("(slice-17) detail header renders the tags row with chips + TagPicker trigger", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response(
          JSON.stringify({
            id: "pb_abc",
            meeting_id: "m_abc",
            free_form_markdown: "",
            objective: "",
            counterparty_profile: "",
            anticipated_topics: "",
            anticipated_objections: "",
            talking_points: "",
            red_lines: "",
            created_at: "2026-05-07T10:00:00Z",
            updated_at: "2026-05-07T10:00:00Z",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.startsWith("/api/tags")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          ...SAMPLE_MEETING,
          tags: [{ id: "tag_a", name: "客戶X", color: "#DDD6FE" }],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    await renderInRouter();
    const row = await screen.findByTestId("meeting-detail-tags-row");
    expect(row.textContent).toContain("客戶X");
    expect(screen.getByTestId("tag-picker-trigger")).toBeDefined();
  });
});

// ─── Slice-06: Start/End Meeting buttons + capture indicator + transcript ─

class _MockSessionWS {
  static instances: _MockSessionWS[] = [];
  url: string;
  readyState = 0;
  sent: string[] = [];
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    _MockSessionWS.instances.push(this);
  }
  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
  simulateMessage(payload: object): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }
}

describe("MeetingDetail slice-06 session UI", () => {
  beforeEach(() => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response(
          JSON.stringify({
            id: "pb_abc",
            meeting_id: "m_abc",
            free_form_markdown: "",
            objective: "",
            counterparty_profile: "",
            anticipated_topics: "",
            anticipated_objections: "",
            talking_points: "",
            red_lines: "",
            created_at: "2026-05-09T10:00:00Z",
            updated_at: "2026-05-09T10:00:00Z",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
    // @ts-expect-error: substitute WebSocket
    globalThis.WebSocket = _MockSessionWS;
    _MockSessionWS.instances = [];
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("clicking Start Meeting opens WS, capture indicator becomes active, transcript renders", async () => {
    const user = userEvent.setup();
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^開始會議$/ }));
    expect(_MockSessionWS.instances).toHaveLength(1);

    // Server says meeting started.
    const ws = _MockSessionWS.instances[0]!;
    await waitFor(() => {
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_abc" });
      // Slice-7: two pills (me + counterparty); both should be in `active` state.
      const pills = screen.getAllByTestId("capture-indicator");
      expect(pills).toHaveLength(2);
      for (const pill of pills) {
        expect(pill.dataset.state).toBe("active");
      }
    });

    // Transcript chunk arrives → renders in TranscriptPane.
    ws.simulateMessage({
      type: "transcript_chunk",
      meeting_id: "m_abc",
      speaker: "me",
      text: "what a fine morning",
      started_at: "2026-05-09T10:00:00Z",
      ended_at: "2026-05-09T10:00:10Z",
      asr_provider_used: "whisper",
      confidence: 0.9,
    });
    await waitFor(() => {
      expect(screen.getByText("what a fine morning")).toBeDefined();
    });
  });

  test("clicking End Meeting sends end_meeting frame", async () => {
    const user = userEvent.setup();
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^開始會議$/ }));
    const ws = _MockSessionWS.instances[0]!;
    await waitFor(() => {
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_abc" });
      // Slice-7: two pills (me + counterparty); both should be in `active` state.
      const pills = screen.getAllByTestId("capture-indicator");
      expect(pills).toHaveLength(2);
      for (const pill of pills) {
        expect(pill.dataset.state).toBe("active");
      }
    });

    await user.click(screen.getByRole("button", { name: /^結束會議$/ }));
    const lastSent = ws.sent[ws.sent.length - 1] ?? "";
    expect(JSON.parse(lastSent)).toEqual({ type: "end_meeting", meeting_id: "m_abc" });
  });

  test("End button is hidden until session is in_progress (slice-7 round 3)", async () => {
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    // Slice-7 round 3: instead of a disabled End button, the button is
    // hidden entirely while phase is idle/connecting/ending/ended/error,
    // so the user can't accidentally click it twice during draining.
    expect(screen.queryByRole("button", { name: /^結束會議$/ })).toBeNull();
  });

  // ─── Slice-08: AdvisorPane integration into the detail page ─────────

  test("AdvisorPane is mounted; placeholder string is gone; Get Advice appears once in_progress", async () => {
    const user = userEvent.setup();
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    // Slice-7 placeholder text MUST be gone now that the real AdvisorPane mounts.
    expect(screen.queryByText(/Tactical advisor 將在 Slice 8 上線/)).toBeNull();
    expect(screen.queryByTestId("advisor-placeholder")).toBeNull();

    // Pre-session: empty state visible, Get Advice button hidden.
    expect(screen.getAllByTestId("advisor-pane-empty").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("get-advice-button")).toBeNull();

    // Drive the session into in_progress.
    await user.click(screen.getByRole("button", { name: /^開始會議$/ }));
    const ws = _MockSessionWS.instances[0]!;
    await waitFor(() => {
      ws.simulateMessage({ type: "meeting_started", meeting_id: "m_abc" });
      expect(screen.queryByTestId("get-advice-button")).not.toBeNull();
    });
  });

  test("AdvisorPane shows empty state when meeting is scheduled (no Get Advice button)", async () => {
    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    // The AdvisorPane is rendered in BOTH the columns and the stack
    // viewports (responsive layout); both produce the empty state element.
    const empties = screen.getAllByTestId("advisor-pane-empty");
    expect(empties.length).toBeGreaterThan(0);
    expect(screen.queryByTestId("get-advice-button")).toBeNull();
  });

  // ─── Slice-09: chat history hydrate + cache invalidate ─────────────

  test("AdvisorPane renders persisted chat history bubbles on mount via React Query", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response(
          JSON.stringify([
            {
              id: "cm_1",
              meeting_id: "m_abc",
              role: "user",
              content: "對方剛說的話怎麼回",
              created_at: "2026-05-09T10:00:00Z",
            },
            {
              id: "cm_2",
              meeting_id: "m_abc",
              role: "advisor",
              content: "建議內容",
              created_at: "2026-05-09T10:00:01Z",
            },
          ]),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.includes("/playbook")) {
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();

    // Both bubbles should appear once the React Query GET resolves.
    await waitFor(() => {
      const bubbles = screen.queryAllByTestId("chat-bubble");
      // Slice-7 dual layouts mount AdvisorPane twice; expect 2 bubbles per
      // mount, so ≥ 2 total.
      expect(bubbles.length).toBeGreaterThanOrEqual(2);
    });

    expect(screen.getAllByTestId("chat-bubble")[0]!.textContent).toContain("對方剛說的話怎麼回");
  });

  test("advice_done causes a follow-up GET /chat_messages refetch (cache invalidation)", async () => {
    const user = userEvent.setup();
    let chatGetCount = 0;
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        chatGetCount += 1;
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    await waitFor(() => {
      expect(chatGetCount).toBeGreaterThanOrEqual(1);
    });
    const initialCount = chatGetCount;

    // Drive into in_progress, then simulate a complete advice cycle on
    // the first WS instance (slice-7 dual layout creates 2 — both share
    // the same hook so triggering one is enough).
    const startButtons = screen.getAllByRole("button", { name: /^開始會議$/ });
    await user.click(startButtons[0]!);
    const ws = _MockSessionWS.instances[0]!;
    ws.simulateMessage({ type: "meeting_started", meeting_id: "m_abc" });

    // Click Get Advice — generates a request_id we can use for the
    // matching advice_done frame.
    await waitFor(() => {
      expect(screen.queryAllByTestId("get-advice-button").length).toBeGreaterThan(0);
    });
    await user.click(screen.getAllByTestId("get-advice-button")[0]!);

    // Pull the request_id from the request_advice frame the hook just sent.
    const sentReqAdvice = ws.sent
      .map((s) => JSON.parse(s) as { type: string; request_id?: string })
      .find((m) => m.type === "request_advice");
    expect(sentReqAdvice).toBeDefined();
    const requestId = sentReqAdvice!.request_id!;

    ws.simulateMessage({ type: "advice_done", request_id: requestId });

    await waitFor(() => {
      expect(chatGetCount).toBeGreaterThan(initialCount);
    });
  });

  // ─── Slice-10: Workspace / Summary tabs ─────────────────────────────

  test("workspace tab is active by default; summary tab is disabled when meeting not completed", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    // Workspace tab content is visible (post-Phase-5: single `workspace`
    // testid carries `data-layout` for grid mode).
    const workspace = screen.queryByTestId("workspace");
    expect(workspace).not.toBeNull();
    expect(workspace?.getAttribute("data-layout")).toMatch(/^(columns|stack)$/);
    // Summary tab trigger is disabled (meeting status = "scheduled").
    const summaryTab = screen.getByTestId("detail-tab-summary") as HTMLButtonElement;
    expect(summaryTab.disabled).toBe(true);
    // SummaryPane is NOT mounted.
    expect(screen.queryByTestId("summary-pane")).toBeNull();
  });

  test("summary tab enabled and clickable when meeting status is completed", async () => {
    const user = userEvent.setup();
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/playbook")) {
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.endsWith("/summary")) {
        // 404 → SummaryPane renders the empty state.
        return new Response(JSON.stringify({ error_code: "summary.not_found", message: "no" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/transcript_chunks")) {
        // detail.tsx loads transcript history for completed meetings via
        // rowToMessage(); without an array stub the helper crashes on
        // `{}.map`.
        return new Response("[]", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ...SAMPLE_MEETING, status: "completed" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    const summaryTab = screen.getByTestId("detail-tab-summary") as HTMLButtonElement;
    expect(summaryTab.disabled).toBe(false);

    await user.click(summaryTab);

    // SummaryPane mounts; the empty state appears (404 from /summary).
    await waitFor(() => {
      expect(screen.getByTestId("summary-pane")).toBeDefined();
    });
    await waitFor(() => {
      expect(screen.getByTestId("summary-empty")).toBeDefined();
    });
  });

  // ─── Slice meetings-ux-revamp task 5.2 — BackLink + prev/next nav ───

  test("(5.2) MetadataCard contains the prev/next nav group", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByTestId("meeting-metadata-card")).toBeDefined();
    });
    const card = screen.getByTestId("meeting-metadata-card");
    const nav = card.querySelector('[data-testid="meeting-prev-next-nav"]');
    expect(nav).not.toBeNull();
    // Cache-only lookup: detail test fixture doesn't seed the meetings list
    // cache, so both arrows render disabled here. BackLink still mounts.
    expect(card.querySelector('[data-testid="back-link"]')).not.toBeNull();
  });

  test("(5.2) standalone BackLink row above MetadataCard is removed", async () => {
    fetchHandler = async (url) => {
      if (url.includes("/chat_messages")) {
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderInRouter();
    await waitFor(() => {
      expect(screen.getByTestId("meeting-metadata-card")).toBeDefined();
    });
    // The detail page now renders exactly one BackLink — the one inside
    // the MetadataCard's nav group. No standalone BackLink row.
    const backLinks = document.querySelectorAll('[data-testid="back-link"]');
    expect(backLinks.length).toBe(1);
  });
});
