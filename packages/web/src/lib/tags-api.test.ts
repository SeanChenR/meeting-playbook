/**
 * tags-api wrapper tests — slice-17 task 5.1.
 *
 * Mocks `fetch` and asserts:
 *   (a) the happy path resolves with the parsed payload
 *   (b) a 422 response throws `ApiError` with `errorCode === "tag.name_taken"`
 *   (c) a 404 response throws `ApiError` with `errorCode === "tag.not_found"`
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { ApiError, attachTag, createTag, listTags, type Tag } from "./tags-api";

const ORIGINAL_FETCH = globalThis.fetch;

function _mock(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const final: Response = {
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => ({}),
    ...response,
  } as Response;
  globalThis.fetch = (async () => final) as typeof fetch;
}

describe("tags-api", () => {
  beforeEach(() => {
    // Reset between tests.
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
  });

  test("listTags resolves with array on 200", async () => {
    const sample: Tag[] = [
      {
        id: "tag_1",
        user_id: "u_a",
        name: "客戶X",
        color: "#DDD6FE",
        created_at: "2026-05-15T00:00:00Z",
      },
    ];
    _mock({ ok: true, status: 200, json: async () => sample });
    const result = await listTags();
    expect(result).toEqual(sample);
  });

  test("createTag rejects with ApiError on 422 name_taken", async () => {
    _mock({
      ok: false,
      status: 422,
      json: async () => ({
        error_code: "tag.name_taken",
        message: "Tag name '客戶X' already exists",
      }),
    });
    try {
      await createTag({ name: "客戶X", color: "#DDD6FE" });
      throw new Error("expected createTag to throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).errorCode).toBe("tag.name_taken");
      expect((err as ApiError).status).toBe(422);
    }
  });

  test("attachTag rejects with ApiError on 404 tag.not_found", async () => {
    _mock({
      ok: false,
      status: 404,
      json: async () => ({
        error_code: "tag.not_found",
        message: "Tag not found",
      }),
    });
    try {
      await attachTag("m_x", "tag_missing");
      throw new Error("expected attachTag to throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).errorCode).toBe("tag.not_found");
      expect((err as ApiError).status).toBe(404);
    }
  });
});
