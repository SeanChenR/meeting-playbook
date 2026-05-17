/**
 * Per-meeting export client (slice-22-export-bundle).
 *
 * `exportMeeting(meetingId, expectedFilename)` triggers a browser-streamed
 * download of the ZIP bundle:
 *
 *   1. HEAD `/api/meetings/{id}/export` — cheap preflight. If the server
 *      returns a non-2xx we read the envelope body via a follow-up GET
 *      so the caller can surface `error_code` via `localizedErrorMessage`.
 *   2. On 2xx HEAD, build a hidden `<a download>` anchor that points at
 *      the same URL and click it. The browser then streams the ZIP
 *      directly to disk — no `await resp.blob()`, no Blob URL, no
 *      buffering of the entire ZIP in JavaScript memory.
 *
 * Why HEAD-then-anchor (Gemini PR #38 review #3): the previous
 * implementation buffered the whole response via `resp.blob()` so it
 * could parse the JSON error envelope on failure. For a 30-minute
 * dual-channel meeting that's ~60 MiB resident in the tab; mobile users
 * could see the tab crash. Streaming via anchor `download` keeps the
 * happy path memory-flat at the cost of a single extra HEAD request
 * for the preflight error check.
 */

import { MeetingApiError } from "./meetings-api";

async function _envelopeError(resp: Response): Promise<MeetingApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore — keep defaults
  }
  return new MeetingApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function exportMeeting(meetingId: string, expectedFilename: string): Promise<void> {
  const url = `/api/meetings/${encodeURIComponent(meetingId)}/export`;

  // Preflight: HEAD is cheap and exposes the same 404 / 401 codes as the
  // streaming GET. We DON'T read the body here (HEAD has none); when the
  // status is non-2xx we re-fetch via GET to grab the envelope JSON for
  // a localized error message.
  const head = await fetch(url, { method: "HEAD" });
  if (!head.ok) {
    const get = await fetch(url, { method: "GET" });
    throw await _envelopeError(get);
  }

  // Happy path: hand the URL to a hidden anchor and let the browser
  // stream the ZIP straight to the user's downloads folder. No Blob.
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = expectedFilename;
  anchor.rel = "noopener";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    document.body.removeChild(anchor);
  }
}
