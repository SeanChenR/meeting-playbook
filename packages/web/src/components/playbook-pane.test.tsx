import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { PlaybookPane } from "./playbook-pane";

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("{}", { status: 200 });
const originalFetch = globalThis.fetch;

const SAMPLE = (overrides: Partial<Record<string, string>> = {}) => ({
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
  await waitFor(() => {
    expect(screen.getByLabelText(/自由格式 Markdown/)).toBeDefined();
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

  test("renders the free-form textarea by default", async () => {
    await renderPane();
    expect(screen.getByLabelText(/自由格式 Markdown/)).toBeDefined();
    // Slice-7 round 3: structured tab removed entirely.
    expect(screen.queryByLabelText("目標")).toBeNull();
    expect(screen.queryByRole("button", { name: /^結構化$/ })).toBeNull();
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
    await user.type(screen.getByLabelText(/自由格式 Markdown/), "# brief");
    await user.click(screen.getByRole("button", { name: /^儲存$/ }));

    await waitFor(() => {
      expect(putCount).toBe(1);
    });
    expect(putBody?.free_form_markdown).toBe("# brief");
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

  test("freeform tab exposes Edit/Preview sub-toggle and renders markdown in preview", async () => {
    const user = userEvent.setup();
    await renderPane();

    expect(screen.getByTestId("freeform-edit-tab")).toBeDefined();
    expect(screen.getByTestId("freeform-preview-tab")).toBeDefined();

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
});
