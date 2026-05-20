import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { PlaybookPane } from "./playbook-pane";

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("{}", { status: 200 });
const originalFetch = globalThis.fetch;

const SAMPLE = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: "pb_test",
  meeting_id: "m_test",
  free_form_markdown: "",
  objective: "",
  counterparty_profile: "",
  anticipated_topics: "",
  anticipated_objections: "",
  talking_points: "",
  red_lines: "",
  created_at: "2026-05-07T10:00:00Z",
  updated_at: "2026-05-07T10:00:00Z",
  previous_free_form_markdown: null as string | null,
  previous_updated_at: null as string | null,
  has_previous_version: false,
  ...overrides,
});

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

async function renderPane(): Promise<void> {
  render(
    <Wrapper>
      <PlaybookPane meetingId="m_test" />
    </Wrapper>,
  );
  // Slice-26 D1: mount default is Preview, not Edit — wait for the
  // preview tab (always rendered) instead of the textarea (Edit-mode only).
  await waitFor(() => {
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();
  });
}

describe("PlaybookPane", () => {
  beforeEach(() => {
    fetchHandler = async () =>
      new Response(JSON.stringify(SAMPLE()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders rendered markdown preview by default (slice-26 D1)", async () => {
    await renderPane();
    // Mount default is Preview: markdown-preview is present, textarea is NOT in DOM.
    expect(screen.getByTestId("markdown-preview")).toBeDefined();
    expect(screen.queryByLabelText(/自由格式 Markdown/)).toBeNull();
    // Slice-7 round 3: structured tab removed entirely.
    expect(screen.queryByLabelText("目標")).toBeNull();
    expect(screen.queryByRole("button", { name: /^結構化$/ })).toBeNull();
    // aria-pressed: preview is active, edit is not.
    expect(screen.getByTestId("freeform-preview-tab").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("freeform-edit-tab").getAttribute("aria-pressed")).toBe("false");
  });

  test("clicking Edit tab swaps preview for textarea; clicking Preview swaps back (slice-26 D3)", async () => {
    const user = userEvent.setup();
    await renderPane();

    // Start: preview visible, textarea absent.
    expect(screen.getByTestId("markdown-preview")).toBeDefined();
    expect(screen.queryByLabelText(/自由格式 Markdown/)).toBeNull();

    // Click Edit → textarea mounts, preview unmounts.
    await user.click(screen.getByTestId("freeform-edit-tab"));
    expect(screen.getByLabelText(/自由格式 Markdown/)).toBeDefined();
    expect(screen.queryByTestId("markdown-preview")).toBeNull();
    expect(screen.getByTestId("freeform-edit-tab").getAttribute("aria-pressed")).toBe("true");

    // Click Preview again → preview re-mounts, textarea unmounts.
    await user.click(screen.getByTestId("freeform-preview-tab"));
    expect(screen.getByTestId("markdown-preview")).toBeDefined();
    expect(screen.queryByLabelText(/自由格式 Markdown/)).toBeNull();
  });

  test("Edit → modify → switch back to Preview without losing draft (slice-26 D3)", async () => {
    const user = userEvent.setup();
    await renderPane();

    await user.click(screen.getByTestId("freeform-edit-tab"));
    const textarea = screen.getByLabelText(/自由格式 Markdown/) as HTMLTextAreaElement;
    await user.type(textarea, "# Draft");
    expect(textarea.value).toBe("# Draft");

    await user.click(screen.getByTestId("freeform-preview-tab"));
    expect(screen.getByTestId("markdown-preview").querySelector("h1")?.textContent).toBe("Draft");

    // Switch back to Edit — draft preserved.
    await user.click(screen.getByTestId("freeform-edit-tab"));
    expect((screen.getByLabelText(/自由格式 Markdown/) as HTMLTextAreaElement).value).toBe(
      "# Draft",
    );
  });

  test("save button posts free_form_markdown plus empty placeholders for the other six fields", async () => {
    const user = userEvent.setup();
    let putBody: Record<string, unknown> | null = null;
    let putCount = 0;
    fetchHandler = async (_, init) => {
      if (init?.method === "PUT") {
        putCount += 1;
        putBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        return new Response(JSON.stringify(SAMPLE(putBody as Partial<Record<string, string>>)), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(SAMPLE()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await renderPane();
    // Slice-26 D5: mount default is Preview; need to click Edit first to access the textarea.
    await user.click(screen.getByTestId("freeform-edit-tab"));
    await user.type(screen.getByLabelText(/自由格式 Markdown/), "# brief");
    await user.click(screen.getByRole("button", { name: /^儲存$/ }));

    await waitFor(() => {
      expect(putCount).toBe(1);
    });
    expect((putBody as Record<string, unknown> | null)?.free_form_markdown).toBe("# brief");
    // Backend schema still requires all 7 fields — non-freeform fields are
    // sent as the GET-loaded values (or empty strings when absent).
    expect(putBody).toHaveProperty("objective");
    expect(putBody).toHaveProperty("counterparty_profile");
    expect(putBody).toHaveProperty("anticipated_topics");
    expect(putBody).toHaveProperty("anticipated_objections");
    expect(putBody).toHaveProperty("talking_points");
    expect(putBody).toHaveProperty("red_lines");

    await waitFor(() => {
      expect(screen.getByText(/已儲存/)).toBeDefined();
    });
  });

  // ─── Slice 7 round 2 ─────────────────────────────────────────────

  test("(6.4) Pane shell renders + AI draft badge visible", async () => {
    await renderPane();
    expect(screen.getByTestId("playbook-pane")).toBeDefined();
    expect(screen.getByTestId("pane-accent")).toBeDefined();
    // refactor-meeting-detail-three-column 1.2: zh-TW playbook.heading → "劇本"
    expect(screen.getByTestId("pane-title").textContent).toBe("劇本");
    expect(screen.getByTestId("playbook-ai-draft-badge")).toBeDefined();
  });

  test("freeform tab exposes Edit/Preview sub-toggle and renders markdown in preview", async () => {
    const user = userEvent.setup();
    await renderPane();

    expect(screen.getByTestId("freeform-edit-tab")).toBeDefined();
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();

    // Slice-26 D5: mount default is Preview; click Edit before typing.
    await user.click(screen.getByTestId("freeform-edit-tab"));
    const freeform = screen.getByLabelText(/自由格式 Markdown/);
    await user.type(freeform, "# Goals");

    await user.click(screen.getByTestId("freeform-preview-tab"));
    const preview = screen.getByTestId("markdown-preview");
    expect(preview.querySelector("h1")?.textContent).toBe("Goals");

    await user.click(screen.getByTestId("freeform-edit-tab"));
    expect((screen.getByLabelText(/自由格式 Markdown/) as HTMLTextAreaElement).value).toBe(
      "# Goals",
    );
  });

  // ─── Slice-23: diff sub-mode integration ──────────────────────────────

  test("(5.1) diff sub-tab is NOT rendered when has_previous_version is false", async () => {
    // SAMPLE default has has_previous_version=false; baseline.
    await renderPane();
    expect(screen.getByTestId("freeform-edit-tab")).toBeDefined();
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();
    expect(screen.queryByTestId("freeform-diff-tab")).toBeNull();
  });

  test("(5.1) diff sub-tab IS rendered when has_previous_version is true", async () => {
    fetchHandler = async () =>
      new Response(
        JSON.stringify(
          SAMPLE({
            free_form_markdown: "v2",
            previous_free_form_markdown: "v1",
            has_previous_version: true,
          }),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    await renderPane();
    expect(screen.getByTestId("freeform-edit-tab")).toBeDefined();
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();
    expect(screen.getByTestId("freeform-diff-tab")).toBeDefined();
  });

  test("(5.2) regenerate auto-switches to diff mode when content changed", async () => {
    const user = userEvent.setup();
    // First GET: stale (so regenerate button shows) + no snapshot yet.
    // Then POST regenerate: returns new content with previous_* populated.
    let regenerateCalled = false;
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        regenerateCalled = true;
        return new Response(
          JSON.stringify(
            SAMPLE({
              free_form_markdown: "v2",
              previous_free_form_markdown: "v1",
              has_previous_version: true,
              is_stale: false,
            }),
          ),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(
        JSON.stringify(
          SAMPLE({
            free_form_markdown: "v1",
            is_stale: true,
          }),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };
    await renderPane();

    // Banner present → click regenerate → confirm dialog opens.
    await user.click(screen.getByTestId("playbook-stale-regenerate-button"));
    const dialog = await screen.findByRole("alertdialog");
    // Click the confirm button INSIDE the dialog.
    await user.click(within(dialog).getByRole("button", { name: "重新生成" }));

    await waitFor(() => {
      expect(regenerateCalled).toBe(true);
    });
    // After regenerate the pane should auto-switch to diff mode.
    await waitFor(() => {
      expect(screen.getByTestId("playbook-diff-viewer")).toBeDefined();
    });
  });

  test("(5.3) snapshot disappearance from Diff falls back to Preview, not Edit (slice-26 D2)", async () => {
    // Test-local QueryClient so we can `invalidateQueries` directly after
    // flipping the fetch handler. The shared Wrapper creates its own client
    // per render which we cannot reach.
    const user = userEvent.setup();
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    fetchHandler = async () =>
      new Response(
        JSON.stringify(
          SAMPLE({
            free_form_markdown: "v2",
            previous_free_form_markdown: "v1",
            has_previous_version: true,
          }),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      );

    render(
      <QueryClientProvider client={client}>
        <PlaybookPane meetingId="m_test" />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("freeform-diff-tab")).toBeDefined();
    });
    await user.click(screen.getByTestId("freeform-diff-tab"));
    await waitFor(() => {
      expect(screen.getByTestId("playbook-diff-viewer")).toBeDefined();
    });

    // Snapshot disappears: next GET returns has_previous_version=false.
    fetchHandler = async () =>
      new Response(
        JSON.stringify(SAMPLE({ free_form_markdown: "v2", has_previous_version: false })),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    // Invalidate so the useQuery refetches with the new handler's response.
    await client.invalidateQueries({ queryKey: ["playbook", "m_test"] });

    await waitFor(() => {
      // Diff button gone (has_previous_version === false).
      expect(screen.queryByTestId("freeform-diff-tab")).toBeNull();
    });
    // Fallback target is preview, NOT edit.
    expect(screen.getByTestId("freeform-preview-tab").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("freeform-edit-tab").getAttribute("aria-pressed")).toBe("false");
  });

  test("(5.2) regenerate does NOT auto-switch when current === previous", async () => {
    const user = userEvent.setup();
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify(
            SAMPLE({
              free_form_markdown: "v1",
              previous_free_form_markdown: "v1",
              has_previous_version: true,
              is_stale: false,
            }),
          ),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(SAMPLE({ free_form_markdown: "v1", is_stale: true })), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    await renderPane();

    await user.click(screen.getByTestId("playbook-stale-regenerate-button"));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "重新生成" }));

    // No auto-switch — diff viewer should NOT mount.
    await waitFor(() => {
      // Sub-tab might show (has_previous_version=true) but viewer should not.
      expect(screen.queryByTestId("playbook-diff-viewer")).toBeNull();
    });
  });
});
