/**
 * UploadDialog tests — slice-14 task 5.4.
 *
 * Per spec scenarios under `Upload dialog drives the tus session and
 * progress polling`:
 *   - successful flow ends with closed dialog and meeting query invalidated
 *   - upload failure surfaces localized error message + retry available
 *
 * The real `uploadOfflineAudio` and `getOfflineIngestProgress` are injected
 * via component props so this test runs against a deterministic stub.
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { type MeetingDetail } from "@/lib/meetings-api";
import { type OfflineIngestProgress } from "@/lib/offline-ingest-api";
import { OfflineIngestUploadError, type UploadOfflineAudioOptions } from "@/lib/tus-uploader";

import { UploadDialog } from "./UploadDialog";

afterEach(() => {
  cleanup();
});

function _withQueryClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function _meeting(): MeetingDetail {
  return {
    id: "m_x",
    user_id: "u_x",
    title: "dialog test",
    counterparty_display_name: "C",
    me_display_name: "M",
    status: "scheduled",
    asr_provider: "qwen3",
    calendar_event_id: null,
    created_at: "2026-05-10T09:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: "2026-05-10T09:00:00Z",
    scheduled_end_at: "2026-05-10T10:00:00Z",
    recordings_available: false,
    rerun_asr_pending: false,
  };
}

function _makeFile(name = "sample.mp3"): File {
  return new File([new Uint8Array(64)], name, { type: "audio/mpeg" });
}

describe("UploadDialog", () => {
  test("happy flow ends with onClose called when polling reports completed", async () => {
    let capturedUploadOpts: UploadOfflineAudioOptions | null = null;
    const uploader = (opts: UploadOfflineAudioOptions) => {
      capturedUploadOpts = opts;
      return { abort: async () => undefined };
    };

    const progressResponses: OfflineIngestProgress[] = [
      { state: "transcoding" },
      { state: "asr_running", chunks_processed: 1, chunks_total: 2 },
      { state: "completed", chunks_processed: 2, chunks_total: 2 },
    ];
    const progressFetcher = mock(async (_meetingId: string) => {
      return progressResponses.shift() ?? { state: "completed" };
    });

    const onClose = mock(() => undefined);

    render(
      _withQueryClient(
        <UploadDialog
          meeting={_meeting()}
          open
          onClose={onClose}
          uploader={uploader}
          progressFetcher={
            progressFetcher as unknown as typeof import("@/lib/offline-ingest-api").getOfflineIngestProgress
          }
          pollIntervalMs={5}
        />,
      ),
    );

    // Pick a file and click Start.
    const fileInput = screen.getByLabelText(/音檔/i) as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [_makeFile()] } });

    fireEvent.click(screen.getByRole("button", { name: /開始上傳/ }));

    // Uploader should have been invoked with the right meeting id + file.
    await waitFor(() => expect(capturedUploadOpts).not.toBeNull());
    expect(capturedUploadOpts!.meetingId).toBe("m_x");
    expect(capturedUploadOpts!.file.name).toBe("sample.mp3");

    // Drive the upload to completion via the captured callbacks.
    act(() => {
      capturedUploadOpts!.onProgress?.({ bytesUploaded: 64, bytesTotal: 64 });
      capturedUploadOpts!.onComplete?.();
    });

    // Polling should fire and eventually transition to completed → onClose called.
    await waitFor(() => expect(onClose).toHaveBeenCalled(), { timeout: 500 });
  });

  test("upload error surfaces localized message + Start button re-enables on Retry", async () => {
    let capturedUploadOpts: UploadOfflineAudioOptions | null = null;
    const uploader = (opts: UploadOfflineAudioOptions) => {
      capturedUploadOpts = opts;
      return { abort: async () => undefined };
    };

    render(
      _withQueryClient(
        <UploadDialog
          meeting={_meeting()}
          open
          onClose={() => undefined}
          uploader={uploader}
          progressFetcher={mock(async () => ({ state: "completed" }))}
          pollIntervalMs={5}
        />,
      ),
    );

    const fileInput = screen.getByLabelText(/音檔/i) as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [_makeFile()] } });
    fireEvent.click(screen.getByRole("button", { name: /開始上傳/ }));

    await waitFor(() => expect(capturedUploadOpts).not.toBeNull());

    act(() => {
      capturedUploadOpts!.onError?.(
        new OfflineIngestUploadError(
          "offline_ingest.unsupported_format",
          "ignored — UI uses localized message",
          422,
        ),
      );
    });

    // Localized error from `errors.offline_ingest.unsupported_format` — scope
    // the search to the alert region so the dropzone's "wav / mp3" hint text
    // doesn't trigger a multiple-match.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/音檔格式不支援/);

    // Retry brings us back to the Start state.
    fireEvent.click(screen.getByRole("button", { name: /重試/ }));
    expect(screen.getByRole("button", { name: /開始上傳/ })).toBeDefined();
  });
});
