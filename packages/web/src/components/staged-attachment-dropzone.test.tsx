/**
 * StagedAttachmentDropzone component tests — slice-24 task 7.1.
 *
 * Per spec meeting-attachment ADDED requirement
 * "Frontend StagedAttachmentDropzone uploads to staging and lists current
 * staged":
 *  - Renders the dropzone unconditionally (no invisible empty state).
 *  - Lists current staged attachments with a per-row remove button.
 *  - Dropping a file → upload mutation fires; on success the new id is
 *    pushed into `selectedIds` via `onChange`.
 *  - Clicking remove → delete mutation fires; the row disappears from
 *    the list AND `onChange` is invoked without that id.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import "../test-setup";
import "../lib/i18n";

import type { Attachment, PendingAttachment } from "../lib/attachments-api";
import { StagedAttachmentDropzone } from "./staged-attachment-dropzone";

afterEach(() => {
  cleanup();
});

function _wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function _row(over: Partial<PendingAttachment> = {}): PendingAttachment {
  return {
    id: "att_existing",
    kind: "pdf",
    original_name: "existing.pdf",
    bytes: 1024,
    uploaded_at: "2026-05-17T09:00:00Z",
    ...over,
  };
}

function _makeFile(name = "drop.pdf"): File {
  return new File([new Uint8Array(2048)], name, { type: "application/pdf" });
}

function _makeFileWithSize(name: string, sizeBytes: number, mimeType = "application/pdf"): File {
  return new File([new Uint8Array(sizeBytes)], name, { type: mimeType });
}

describe("StagedAttachmentDropzone", () => {
  test("renders dropzone unconditionally when no staged attachments exist", async () => {
    const list = mock(async (): Promise<PendingAttachment[]> => []);
    const onChange = mock(() => undefined);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={[]}
          onChange={onChange}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(list).toHaveBeenCalled());

    // Dropzone always renders; no invisible empty state.
    expect(screen.queryByTestId("staged-dropzone-area")).not.toBeNull();
  });

  test("renders existing staged rows with a remove button", async () => {
    const list = mock(async () => [
      _row({ id: "att_a", original_name: "a.pdf" }),
      _row({ id: "att_b", original_name: "b.pdf" }),
    ]);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={["att_a", "att_b"]}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_a")).not.toBeNull());
    expect(screen.queryByTestId("staged-row-att_b")).not.toBeNull();
    // Each row exposes a remove button.
    expect(screen.queryByTestId("staged-remove-att_a")).not.toBeNull();
    expect(screen.queryByTestId("staged-remove-att_b")).not.toBeNull();
  });

  test("dropping a file triggers upload + pushes new id into selectedIds", async () => {
    const list = mock(async (): Promise<PendingAttachment[]> => []);
    const upload = mock(
      async (_f: File): Promise<Attachment> => ({
        id: "att_new",
        kind: "pdf",
        original_name: "drop.pdf",
        bytes: 2048,
        uploaded_at: "2026-05-17T10:00:00Z",
      }),
    );
    const onChange = mock(() => undefined);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={[]}
          onChange={onChange}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: upload as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(list).toHaveBeenCalled());

    const dropzone = screen.getByTestId("staged-dropzone-area");
    const file = _makeFile("drop.pdf");
    await act(async () => {
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [file] },
      });
    });

    await waitFor(() => expect(upload).toHaveBeenCalled());
    await waitFor(() => {
      const calls = onChange.mock.calls.map((args) => args[0]);
      expect(calls.some((ids) => Array.isArray(ids) && ids.includes("att_new"))).toBe(true);
    });
  });

  // ─── slice-24 task 11.1 — batch upload + truncation ────────────────────
  test("dropping three files within quota uploads all sequentially in drop order", async () => {
    const list = mock(async (): Promise<PendingAttachment[]> => []);
    const callOrder: string[] = [];
    const upload = mock(async (f: File): Promise<Attachment> => {
      callOrder.push(f.name);
      return {
        id: `att_${f.name}`,
        kind: f.type === "application/pdf" ? "pdf" : "image",
        original_name: f.name,
        bytes: f.size,
        uploaded_at: "2026-05-17T10:00:00Z",
      };
    });

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={[]}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: upload as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(list).toHaveBeenCalled());

    const dropzone = screen.getByTestId("staged-dropzone-area");
    const f1 = _makeFileWithSize("a.pdf", 1024 * 1024); // 1 MiB
    const f2 = _makeFileWithSize("b.png", 2 * 1024 * 1024, "image/png");
    const f3 = _makeFileWithSize("c.pdf", 3 * 1024 * 1024);

    await act(async () => {
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [f1, f2, f3] },
      });
    });

    await waitFor(() => expect(upload).toHaveBeenCalledTimes(3));
    expect(callOrder).toEqual(["a.pdf", "b.png", "c.pdf"]);
  });

  test("dropping more than the remaining count quota truncates", async () => {
    // 8 staged → drop 5 → only first 2 should fit (count cap 10)
    const staged = Array.from({ length: 8 }, (_, i) =>
      _row({ id: `att_${i}`, original_name: `s${i}.pdf`, bytes: 1024 }),
    );
    const list = mock(async () => staged);
    const upload = mock(
      async (f: File): Promise<Attachment> => ({
        id: `new_${f.name}`,
        kind: "pdf",
        original_name: f.name,
        bytes: f.size,
        uploaded_at: "2026-05-17T10:00:00Z",
      }),
    );

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={staged.map((s) => s.id)}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: upload as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_0")).not.toBeNull());

    const dropzone = screen.getByTestId("staged-dropzone-area");
    const files = Array.from({ length: 5 }, (_, i) => _makeFileWithSize(`d${i}.pdf`, 1024));

    await act(async () => {
      fireEvent.drop(dropzone, {
        dataTransfer: { files },
      });
    });

    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
    // Inline truncation warning surfaces the dropped + accepted counts.
    await waitFor(() => {
      const err = screen.queryByTestId("staged-error");
      expect(err?.textContent ?? "").toContain("5");
      expect(err?.textContent ?? "").toContain("2");
    });
  });

  test("dropping files that overflow byte quota skips the overflowing ones, accepts the fitting ones", async () => {
    // 1 staged file at 58 MiB (headroom = 2 MiB).
    // Drop [3 MiB, 1 MiB]: the 3 MiB skips (would push to 61), the 1 MiB
    // fits (58 + 1 = 59 ≤ 60). Per design D10 skip-and-continue rule.
    const staged = [_row({ id: "att_big", original_name: "big.pdf", bytes: 58 * 1024 * 1024 })];
    const list = mock(async () => staged);
    const callOrder: string[] = [];
    const upload = mock(async (f: File): Promise<Attachment> => {
      callOrder.push(f.name);
      return {
        id: `new_${f.name}`,
        kind: "pdf",
        original_name: f.name,
        bytes: f.size,
        uploaded_at: "2026-05-17T10:00:00Z",
      };
    });

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={["att_big"]}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: upload as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_big")).not.toBeNull());

    const dropzone = screen.getByTestId("staged-dropzone-area");
    const fBig = _makeFileWithSize("big_drop.pdf", 3 * 1024 * 1024);
    const fSmall = _makeFileWithSize("small_drop.pdf", 1 * 1024 * 1024);

    await act(async () => {
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [fBig, fSmall] },
      });
    });

    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
    expect(callOrder).toEqual(["small_drop.pdf"]);
    // Warning notes 1 dropped, 1 accepted.
    await waitFor(() => {
      const err = screen.queryByTestId("staged-error");
      expect(err?.textContent ?? "").toContain("1");
    });
  });

  test("clicking remove calls deleteStagedAttachment + drops the id", async () => {
    const list = mock(async () => [_row({ id: "att_kill", original_name: "kill.pdf" })]);
    const del = mock(async () => undefined);
    const onChange = mock(() => undefined);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={["att_kill"]}
          onChange={onChange}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: del as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-remove-att_kill")).not.toBeNull());
    await act(async () => {
      fireEvent.click(screen.getByTestId("staged-remove-att_kill"));
    });

    await waitFor(() => expect(del).toHaveBeenCalledWith("att_kill"));
    await waitFor(() => {
      const calls = onChange.mock.calls.map((args) => args[0]);
      expect(calls.some((ids) => Array.isArray(ids) && !ids.includes("att_kill"))).toBe(true);
    });
  });

  // ─── slice-24 task 11.2 — quota counter + at-limit state ────────────────
  test("counter renders current count and bytes formatted", async () => {
    // 3 staged: 1 MiB + 2 MiB + 3 MiB = 6.0 MB; counter shows 3/10 + bytes.
    const list = mock(async () => [
      _row({ id: "a", original_name: "a.pdf", bytes: 1 * 1024 * 1024 }),
      _row({ id: "b", original_name: "b.pdf", bytes: 2 * 1024 * 1024 }),
      _row({ id: "c", original_name: "c.pdf", bytes: 3 * 1024 * 1024 }),
    ]);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={["a", "b", "c"]}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-a")).not.toBeNull());

    const counter = screen.queryByTestId("staged-counter");
    expect(counter).not.toBeNull();
    expect(counter?.textContent ?? "").toContain("3 / 10");
    expect(counter?.textContent ?? "").toContain("60");
  });

  test("at count-limit disables the dropzone and renders at-limit hint", async () => {
    // 10 staged → at-limit by count.
    const staged = Array.from({ length: 10 }, (_, i) =>
      _row({ id: `att_${i}`, original_name: `s${i}.pdf`, bytes: 1024 }),
    );
    const list = mock(async () => staged);
    const upload = mock(async () => _row());

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={staged.map((s) => s.id)}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: upload as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_0")).not.toBeNull());

    // Drop should be ignored — upload mutation never fires.
    const dropzone = screen.getByTestId("staged-dropzone-area");
    await act(async () => {
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [_makeFileWithSize("blocked.pdf", 1024)] },
      });
    });
    // Give React Query a tick to settle if any mutation were queued.
    await new Promise((r) => setTimeout(r, 30));
    expect(upload).not.toHaveBeenCalled();

    // Upload button is disabled.
    const btn = screen.getByTestId("staged-upload-button") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);

    // At-limit hint replaces the empty/dropzone label.
    expect(screen.queryByTestId("staged-at-limit-hint")).not.toBeNull();
  });

  test("at byte-limit disables the dropzone", async () => {
    // 1 staged at 60 MiB → at-limit by byte sum.
    const list = mock(async () => [
      _row({ id: "att_full", original_name: "full.pdf", bytes: 60 * 1024 * 1024 }),
    ]);

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={["att_full"]}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: mock(async () => undefined) as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_full")).not.toBeNull());

    const btn = screen.getByTestId("staged-upload-button") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(screen.queryByTestId("staged-at-limit-hint")).not.toBeNull();
  });

  test("removing from at-limit state re-enables the dropzone", async () => {
    // Start at 10/10 — remove one → counter goes 9/10 and button re-enables.
    const staged = Array.from({ length: 10 }, (_, i) =>
      _row({ id: `att_${i}`, original_name: `s${i}.pdf`, bytes: 1024 }),
    );
    let currentList = [...staged];
    const list = mock(async () => currentList);
    const del = mock(async (id: string) => {
      currentList = currentList.filter((r) => r.id !== id);
    });

    render(
      _wrap(
        <StagedAttachmentDropzone
          selectedIds={staged.map((s) => s.id)}
          onChange={mock(() => undefined)}
          api={{
            listPendingAttachments: list,
            uploadStagedAttachment: mock(async () => _row()) as never,
            deleteStagedAttachment: del as never,
          }}
        />,
      ),
    );
    await waitFor(() => expect(screen.queryByTestId("staged-row-att_0")).not.toBeNull());

    // Pre-condition: at-limit.
    const btnBefore = screen.getByTestId("staged-upload-button") as HTMLButtonElement;
    expect(btnBefore.disabled).toBe(true);

    // Click remove on one row.
    await act(async () => {
      fireEvent.click(screen.getByTestId("staged-remove-att_0"));
    });

    await waitFor(() => expect(del).toHaveBeenCalledWith("att_0"));
    await waitFor(() => {
      const btn = screen.getByTestId("staged-upload-button") as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
    });
    expect(screen.queryByTestId("staged-at-limit-hint")).toBeNull();
    expect(screen.getByTestId("staged-counter").textContent ?? "").toContain("9 / 10");
  });
});
