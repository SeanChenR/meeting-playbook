/**
 * Per-meeting export client (slice-22-export-bundle).
 *
 * `exportMeeting(meetingId, expectedFilename)` does the minimal end-to-end
 * dance for a browser-triggered download of the ZIP bundle:
 *
 *   1. GET `/api/meetings/{id}/export` through the gateway. The dev server's
 *      Vite proxy → Bun gateway → FastAPI chain handles auth + the
 *      `X-User-Id` header injection per ADR-0021.
 *   2. Read the response body as a `Blob`.
 *   3. Create an object URL from the blob, attach it to a hidden
 *      `<a download>` anchor, programmatically click the anchor, then
 *      revoke the URL.
 *
 * Failures arrive as the project `{error_code, message}` envelope; this
 * helper rethrows them as `MeetingApiError` so callers can resolve a
 * localized message via `localizedErrorMessage(errorCode, t)`.
 *
 * The `expectedFilename` argument is used as the anchor's `download`
 * attribute hint — the browser still honours the server's
 * `Content-Disposition` filename when present. We surface this as an
 * explicit argument so the calling component can choose its own naming
 * fallback without coupling the helper to date formatting / i18n.
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
  const resp = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/export`);
  if (!resp.ok) throw await _envelopeError(resp);

  const blob = await resp.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = expectedFilename;
    anchor.rel = "noopener";
    // Anchor must be in the DOM for some browsers to honour the click;
    // hide it visually and drop it afterwards.
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    try {
      anchor.click();
    } finally {
      document.body.removeChild(anchor);
    }
  } finally {
    // Always revoke — leaking blob URLs keeps the blob memory pinned.
    URL.revokeObjectURL(objectUrl);
  }
}
