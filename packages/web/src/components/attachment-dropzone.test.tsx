/**
 * AttachmentDropzone component tests — slice-20a task 5.2.
 *
 * Spec scenarios under "AttachmentDropzone component renders list,
 * dropzone, and progress":
 *   - dropping a file shows progress card 0%→100% and appends a list row
 *   - 422 quota_exceeded renders the localized error message and leaves
 *     the existing list unchanged
 *   - clicking delete removes the row after a successful 204
 *
 * The test injects the API helpers via props so we don't have to mock
 * `globalThis.fetch` or `XMLHttpRequest` across the whole test file.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import "../test-setup";
import "../lib/i18n";

import type { Attachment } from "../lib/attachments-api";

import { AttachmentDropzone } from "./attachment-dropzone";

afterEach(() => {
  cleanup();
});

function _wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function _row(over: Partial<Attachment> = {}): Attachment {
  return {
    id: "att_existing",
    kind: "pdf",
    original_name: "existing.pdf",
    bytes: 1024,
    uploaded_at: "2026-05-10T09:00:00Z",
    ...over,
  };
}

function _makeFile(name = "drop.pdf"): File {
  return new File([new Uint8Array(2048)], name, { type: "application/pdf" });
}

describe("AttachmentDropzone", () => {
  test("renders empty state when there are no attachments", async () => {
    const list = mock(async () => [] as Attachment[]);
    render(
      _wrap(
        <AttachmentDropzone
          meetingId="m_a"
          api={{
            listAttachments: list,
            uploadAttachment: mock(async () => _row()) as never,
            deleteAttachment: mock(async () => undefined) as never,
            getDownloadUrl: (m, a) => `/api/meetings/${m}/attachments/${a}/download`,
          }}
        />,
      ),
    );
    await waitFor(() => expect(list).toHaveBeenCalled());
    // emptyState text — either zh or en is fine, just confirm it's rendered.
    expect(screen.queryByTestId("attachment-empty-state")).not.toBeNull();
  });

  test("dropping a valid PDF resolves to a new row in the list", async () => {
    const list = mock(async () => [] as Attachment[]);
    let progressFn: ((percent: number) => void) | undefined;
    const upload = mock(
      async (_m: string, _f: File, onProgress?: (p: number) => void): Promise<Attachment> => {
        progressFn = onProgress;
        // simulate progress callback being invoked
        onProgress?.(0);
        onProgress?.(50);
        onProgress?.(100);
        return _row({ id: "att_new", original_name: "drop.pdf", bytes: 2048 });
      },
    );

    render(
      _wrap(
        <AttachmentDropzone
          meetingId="m_a"
          api={{
            listAttachments: list,
            uploadAttachment: upload as never,
            deleteAttachment: mock(async () => undefined) as never,
            getDownloadUrl: (m, a) => `/api/meetings/${m}/attachments/${a}/download`,
          }}
        />,
      ),
    );

    await waitFor(() => expect(list).toHaveBeenCalled());

    const input = screen.getByTestId("attachment-file-input") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [_makeFile()] } });
    });

    await waitFor(() => expect(upload).toHaveBeenCalled());
    await waitFor(() => {
      const rows = screen.queryAllByTestId("attachment-row");
      expect(rows.length).toBe(1);
    });

    // progress callback was wired
    expect(progressFn).toBeDefined();
  });

  test("422 quota_exceeded renders localized error and existing list survives", async () => {
    const list = mock(async () => [_row()]);
    const upload = mock(async () => {
      const err = new Error("Per-meeting byte quota exceeded") as Error & {
        errorCode?: string;
        status?: number;
      };
      err.errorCode = "attachment.quota_exceeded";
      err.status = 422;
      throw err;
    });

    render(
      _wrap(
        <AttachmentDropzone
          meetingId="m_a"
          api={{
            listAttachments: list,
            uploadAttachment: upload as never,
            deleteAttachment: mock(async () => undefined) as never,
            getDownloadUrl: (m, a) => `/api/meetings/${m}/attachments/${a}/download`,
          }}
        />,
      ),
    );
    await waitFor(() => expect(list).toHaveBeenCalled());
    // initial row visible
    await waitFor(() => expect(screen.queryAllByTestId("attachment-row").length).toBe(1));

    const input = screen.getByTestId("attachment-file-input") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [_makeFile()] } });
    });

    await waitFor(() => expect(upload).toHaveBeenCalled());

    // Error region surfaces (either Chinese or English localized text — we
    // just confirm the testid is in the DOM with content).
    await waitFor(() => {
      const alert = screen.queryByTestId("attachment-error");
      expect(alert).not.toBeNull();
      expect(alert?.textContent?.length ?? 0).toBeGreaterThan(0);
    });

    // Existing row still there.
    expect(screen.queryAllByTestId("attachment-row").length).toBe(1);
  });

  test("clicking delete removes the row after a successful DELETE", async () => {
    const initial = _row({ id: "att_del" });
    const list = mock(async () => [initial]);
    const del = mock(async () => undefined);

    // Provide a stable confirm() impl so the test doesn't depend on the
    // happy-dom default (which would reject the action).
    const originalConfirm = window.confirm;
    window.confirm = () => true;

    try {
      render(
        _wrap(
          <AttachmentDropzone
            meetingId="m_a"
            api={{
              listAttachments: list,
              uploadAttachment: mock(async () => _row()) as never,
              deleteAttachment: del as never,
              getDownloadUrl: (m, a) => `/api/meetings/${m}/attachments/${a}/download`,
            }}
          />,
        ),
      );
      await waitFor(() => expect(screen.queryAllByTestId("attachment-row").length).toBe(1));

      const delButton = screen.getByTestId("attachment-delete-att_del");
      await act(async () => {
        fireEvent.click(delButton);
      });

      await waitFor(() => expect(del).toHaveBeenCalled());
      await waitFor(() => expect(screen.queryAllByTestId("attachment-row").length).toBe(0));
    } finally {
      window.confirm = originalConfirm;
    }
  });
});
