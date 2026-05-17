/**
 * Unit tests for `attachments-api.ts` (slice-20a task 5.1).
 *
 * Covers:
 *   - listAttachments → fetches `/api/meetings/{id}/attachments` and unwraps `.attachments`
 *   - uploadAttachment → XHR-based, fires `onProgress` at least once, resolves to row
 *   - uploadAttachment 422 → rejects with `AttachmentApiError` carrying `errorCode`
 *   - deleteAttachment → DELETE request with correct URL
 *   - getDownloadUrl → composes the expected path
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";

import {
  AttachmentApiError,
  deleteAttachment,
  getDownloadUrl,
  listAttachments,
  uploadAttachment,
} from "./attachments-api";

const _originalFetch = globalThis.fetch;
const _originalXHR = globalThis.XMLHttpRequest;

beforeEach(() => {
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
  globalThis.XMLHttpRequest = _originalXHR;
});

describe("listAttachments", () => {
  test("returns the `attachments` array from the response envelope", async () => {
    let capturedUrl = "";
    globalThis.fetch = (async (url: string) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          attachments: [
            {
              id: "att_a",
              kind: "pdf",
              original_name: "x.pdf",
              bytes: 100,
              uploaded_at: "2026-05-15T00:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const rows = await listAttachments("m_abc");

    expect(capturedUrl).toBe("/api/meetings/m_abc/attachments");
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("att_a");
  });

  test("throws AttachmentApiError on 404", async () => {
    globalThis.fetch = (async () => {
      return new Response(JSON.stringify({ error_code: "meeting.not_found", message: "no" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await expect(listAttachments("m_x")).rejects.toBeInstanceOf(AttachmentApiError);
  });
});

class FakeXHR {
  upload = {
    onprogress: null as
      | ((evt: { loaded: number; total: number; lengthComputable: boolean }) => void)
      | null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  status = 0;
  responseText = "";
  openedWith: { method: string; url: string } = { method: "", url: "" };
  sentBody: unknown = null;

  open(method: string, url: string, _async: boolean) {
    this.openedWith = { method, url };
  }
  send(body: unknown) {
    this.sentBody = body;
    // simulate upload progress then completion
    queueMicrotask(() => {
      this.upload.onprogress?.({ loaded: 50, total: 100, lengthComputable: true });
      this.upload.onprogress?.({ loaded: 100, total: 100, lengthComputable: true });
      this.status = (this as { _stubStatus?: number })._stubStatus ?? 200;
      this.responseText = (this as { _stubResponse?: string })._stubResponse ?? "{}";
      this.onload?.();
    });
  }
}

describe("uploadAttachment", () => {
  test("resolves with the new row and fires onProgress at least once", async () => {
    let capturedFile: File | null = null;

    class TestXHR extends FakeXHR {
      constructor() {
        super();
        (this as { _stubStatus?: number })._stubStatus = 200;
        (this as { _stubResponse?: string })._stubResponse = JSON.stringify({
          id: "att_new",
          kind: "pdf",
          original_name: "ok.pdf",
          bytes: 100,
          uploaded_at: "2026-05-15T00:00:00Z",
        });
      }
      send(body: unknown) {
        const fd = body as FormData;
        capturedFile = fd.get("file") as File;
        super.send(body);
      }
    }
    globalThis.XMLHttpRequest = TestXHR as unknown as typeof XMLHttpRequest;

    const progressFn = mock(() => undefined);
    const file = new File([new Uint8Array(100)], "ok.pdf", { type: "application/pdf" });

    const att = await uploadAttachment("m_a", file, progressFn);

    expect(att.id).toBe("att_new");
    expect(progressFn).toHaveBeenCalled();
    expect(progressFn.mock.calls.some((args) => args[0] === 0)).toBe(true);
    expect(progressFn.mock.calls.some((args) => args[0] === 100)).toBe(true);
    expect(capturedFile?.name).toBe("ok.pdf");
  });

  test("rejects with AttachmentApiError when backend returns 422 envelope", async () => {
    class TestXHR extends FakeXHR {
      constructor() {
        super();
        (this as { _stubStatus?: number })._stubStatus = 422;
        (this as { _stubResponse?: string })._stubResponse = JSON.stringify({
          error_code: "attachment.quota_exceeded",
          message: "too big",
        });
      }
    }
    globalThis.XMLHttpRequest = TestXHR as unknown as typeof XMLHttpRequest;

    const file = new File([new Uint8Array(100)], "x.pdf", { type: "application/pdf" });

    let thrown: unknown = null;
    try {
      await uploadAttachment("m_a", file);
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(AttachmentApiError);
    expect((thrown as AttachmentApiError).errorCode).toBe("attachment.quota_exceeded");
    expect((thrown as AttachmentApiError).status).toBe(422);
  });
});

describe("deleteAttachment", () => {
  test("sends DELETE with the correct path", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedMethod = init?.method ?? "";
      return new Response(null, { status: 204 });
    }) as unknown as typeof fetch;

    await deleteAttachment("m_abc", "att_z");

    expect(capturedUrl).toBe("/api/meetings/m_abc/attachments/att_z");
    expect(capturedMethod).toBe("DELETE");
  });

  test("throws AttachmentApiError on 404", async () => {
    globalThis.fetch = (async () => {
      return new Response(JSON.stringify({ error_code: "attachment.not_found", message: "nope" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await expect(deleteAttachment("m_a", "att_x")).rejects.toBeInstanceOf(AttachmentApiError);
  });
});

describe("getDownloadUrl", () => {
  test("returns the canonical download path", () => {
    expect(getDownloadUrl("m_abc", "att_z")).toBe("/api/meetings/m_abc/attachments/att_z/download");
  });
});

// ─── Slice-24: staging client functions ─────────────────────────────

describe("uploadStagedAttachment", () => {
  test("posts to /api/attachments/staging and resolves with the new row", async () => {
    let openedUrl = "";
    class TestXHR extends FakeXHR {
      constructor() {
        super();
        (this as { _stubStatus?: number })._stubStatus = 201;
        (this as { _stubResponse?: string })._stubResponse = JSON.stringify({
          id: "att_staged",
          kind: "pdf",
          original_name: "s.pdf",
          bytes: 100,
          uploaded_at: "2026-05-17T00:00:00Z",
        });
      }
      open(method: string, url: string, _async: boolean) {
        openedUrl = url;
        super.open(method, url, _async);
      }
    }
    globalThis.XMLHttpRequest = TestXHR as unknown as typeof XMLHttpRequest;

    const { uploadStagedAttachment } = await import("./attachments-api");
    const file = new File([new Uint8Array(100)], "s.pdf", { type: "application/pdf" });
    const progressFn = mock(() => undefined);

    const att = await uploadStagedAttachment(file, progressFn);

    expect(openedUrl).toBe("/api/attachments/staging");
    expect(att.id).toBe("att_staged");
    expect(progressFn).toHaveBeenCalled();
  });

  test("throws AttachmentApiError on 422 staging_quota_exceeded", async () => {
    class TestXHR extends FakeXHR {
      constructor() {
        super();
        (this as { _stubStatus?: number })._stubStatus = 422;
        (this as { _stubResponse?: string })._stubResponse = JSON.stringify({
          error_code: "attachment.staging_quota_exceeded",
          message: "too many",
        });
      }
    }
    globalThis.XMLHttpRequest = TestXHR as unknown as typeof XMLHttpRequest;

    const { uploadStagedAttachment } = await import("./attachments-api");
    const file = new File([new Uint8Array(100)], "x.pdf", { type: "application/pdf" });

    let thrown: unknown = null;
    try {
      await uploadStagedAttachment(file);
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(AttachmentApiError);
    expect((thrown as AttachmentApiError).errorCode).toBe("attachment.staging_quota_exceeded");
  });
});

describe("deleteStagedAttachment", () => {
  test("sends DELETE to /api/attachments/{id}", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedMethod = init?.method ?? "";
      return new Response(null, { status: 204 });
    }) as unknown as typeof fetch;

    const { deleteStagedAttachment } = await import("./attachments-api");
    await deleteStagedAttachment("att_z");

    expect(capturedUrl).toBe("/api/attachments/att_z");
    expect(capturedMethod).toBe("DELETE");
  });

  test("throws AttachmentApiError on 404", async () => {
    globalThis.fetch = (async () => {
      return new Response(JSON.stringify({ error_code: "attachment.not_found", message: "nope" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const { deleteStagedAttachment } = await import("./attachments-api");
    await expect(deleteStagedAttachment("att_x")).rejects.toBeInstanceOf(AttachmentApiError);
  });
});

describe("listPendingAttachments (slice-24 real endpoint)", () => {
  test("hits /api/attachments?status=pending and unwraps the attachments array", async () => {
    let capturedUrl = "";
    globalThis.fetch = (async (url: string) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          attachments: [
            {
              id: "att_p",
              kind: "pdf",
              original_name: "p.pdf",
              bytes: 100,
              uploaded_at: "2026-05-17T00:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const { listPendingAttachments } = await import("./attachments-api");
    const rows = await listPendingAttachments();
    expect(capturedUrl).toBe("/api/attachments?status=pending");
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("att_p");
  });

  test("returns empty array on non-2xx (graceful fallback preserved)", async () => {
    globalThis.fetch = (async () => new Response(null, { status: 500 })) as unknown as typeof fetch;

    const { listPendingAttachments } = await import("./attachments-api");
    const rows = await listPendingAttachments();
    expect(rows).toEqual([]);
  });
});
