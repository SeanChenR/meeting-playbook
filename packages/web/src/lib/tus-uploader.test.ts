/**
 * Unit tests for the tus-uploader wrapper (slice-14 task 5.1).
 *
 * Verifies the spec scenario clause `Upload dialog drives the tus session`:
 * - successful tus upload → onComplete fires exactly once
 * - tus error with a server envelope → onError surfaces `error_code`
 * - tus progress event → onProgress receives bytesUploaded / bytesTotal
 *
 * `tus.Upload` is replaced with a stub that captures the options bag and
 * lets each test fire the callbacks directly. We never hit the network.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";

let capturedOptions: any = null;

mock.module("tus-js-client", () => ({
  Upload: class FakeTusUpload {
    file: File;
    options: any;
    constructor(file: File, options: any) {
      this.file = file;
      this.options = options;
      capturedOptions = options;
    }
    start() {
      // Tests fire callbacks manually via `capturedOptions`.
    }
    async abort(_terminate: boolean) {
      // No-op.
    }
  },
}));

// Imported AFTER mock.module so the wrapper picks up the fake.
import { OfflineIngestUploadError, uploadOfflineAudio } from "./tus-uploader";

beforeEach(() => {
  capturedOptions = null;
});

afterEach(() => {
  mock.restore();
});

function _makeFile(): File {
  return new File([new Uint8Array(1024)], "sample.mp3", { type: "audio/mpeg" });
}

describe("uploadOfflineAudio", () => {
  test("invokes onComplete once when tus reports success", () => {
    const completes: number[] = [];
    uploadOfflineAudio({
      meetingId: "m_a",
      file: _makeFile(),
      actualStartedAt: new Date("2026-05-14T09:00:00Z"),
      onComplete: () => completes.push(Date.now()),
    });
    expect(capturedOptions).not.toBeNull();
    expect(capturedOptions.endpoint).toBe("/api/meetings/m_a/recordings/offline_upload");
    expect(capturedOptions.metadata.filename).toBe("sample.mp3");
    expect(capturedOptions.metadata.mimetype).toBe("audio/mpeg");
    expect(capturedOptions.metadata.actual_started_at).toBe("2026-05-14T09:00:00.000Z");

    capturedOptions.onSuccess();
    expect(completes.length).toBe(1);
  });

  test("invokes onError with parsed error_code when tus surfaces a server envelope", () => {
    const errors: OfflineIngestUploadError[] = [];
    uploadOfflineAudio({
      meetingId: "m_b",
      file: _makeFile(),
      actualStartedAt: new Date("2026-05-14T09:00:00Z"),
      onError: (err) => errors.push(err),
    });

    capturedOptions.onError({
      message: "Request failed",
      originalResponse: {
        getStatus: () => 422,
        getBody: () =>
          JSON.stringify({
            detail: {
              error_code: "offline_ingest.unsupported_format",
              message: "mimetype not allowed",
            },
          }),
      },
    });

    expect(errors.length).toBe(1);
    expect(errors[0].errorCode).toBe("offline_ingest.unsupported_format");
    expect(errors[0].statusCode).toBe(422);
    expect(errors[0].message).toBe("mimetype not allowed");
  });

  test("invokes onProgress with bytesUploaded and bytesTotal", () => {
    const progresses: Array<{ uploaded: number; total: number }> = [];
    uploadOfflineAudio({
      meetingId: "m_c",
      file: _makeFile(),
      actualStartedAt: new Date("2026-05-14T09:00:00Z"),
      onProgress: ({ bytesUploaded, bytesTotal }) =>
        progresses.push({ uploaded: bytesUploaded, total: bytesTotal }),
    });

    capturedOptions.onProgress(512, 1024);
    capturedOptions.onProgress(1024, 1024);

    expect(progresses).toEqual([
      { uploaded: 512, total: 1024 },
      { uploaded: 1024, total: 1024 },
    ]);
  });
});
