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
});
