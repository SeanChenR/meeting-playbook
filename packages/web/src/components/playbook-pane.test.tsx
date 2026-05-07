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
    // Structured field labels are NOT visible in default view.
    expect(screen.queryByLabelText("目標")).toBeNull();
  });

  test("toggle reveals six labeled structured fields", async () => {
    const user = userEvent.setup();
    await renderPane();
    await user.click(screen.getByRole("button", { name: /^結構化$/ }));

    expect(screen.getByLabelText("目標")).toBeDefined();
    expect(screen.getByLabelText("對方輪廓")).toBeDefined();
    expect(screen.getByLabelText("預期主題")).toBeDefined();
    expect(screen.getByLabelText("預期反對")).toBeDefined();
    expect(screen.getByLabelText("談話要點")).toBeDefined();
    expect(screen.getByLabelText("紅線")).toBeDefined();
  });

  test("switching view does not discard unsaved edits in either side", async () => {
    const user = userEvent.setup();
    await renderPane();

    // Type in free-form view.
    const freeform = screen.getByLabelText(/自由格式 Markdown/);
    await user.type(freeform, "free-form draft");

    // Toggle to structured, type into objective.
    await user.click(screen.getByRole("button", { name: /^結構化$/ }));
    const objective = screen.getByLabelText("目標");
    await user.type(objective, "structured draft");

    // Toggle back to free-form, the previous text is still there.
    await user.click(screen.getByRole("button", { name: /^自由格式$/ }));
    expect((screen.getByLabelText(/自由格式 Markdown/) as HTMLTextAreaElement).value).toBe(
      "free-form draft",
    );

    // Toggle to structured again, the previous typed objective is preserved.
    await user.click(screen.getByRole("button", { name: /^結構化$/ }));
    expect((screen.getByLabelText("目標") as HTMLTextAreaElement).value).toBe("structured draft");
  });

  test("save button issues exactly one PUT carrying all seven fields", async () => {
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

    await user.click(screen.getByRole("button", { name: /^結構化$/ }));
    await user.type(screen.getByLabelText("目標"), "Close Q3");
    await user.type(screen.getByLabelText("紅線"), "no discount below 30%");

    await user.click(screen.getByRole("button", { name: /^儲存$/ }));

    await waitFor(() => {
      expect(putCount).toBe(1);
    });
    expect(putBody).toEqual({
      free_form_markdown: "# brief",
      objective: "Close Q3",
      counterparty_profile: "",
      anticipated_topics: "",
      anticipated_objections: "",
      talking_points: "",
      red_lines: "no discount below 30%",
    });

    // Saved indicator surfaces.
    await waitFor(() => {
      expect(screen.getByText(/已儲存/)).toBeDefined();
    });
  });
});
