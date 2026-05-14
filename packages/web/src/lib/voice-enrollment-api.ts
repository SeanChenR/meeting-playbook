/**
 * Voice enrollment API helper.
 *
 * Wraps `POST /api/voice_enrollment` so the `/settings/voice` route stays
 * focused on UI and recorder concerns. The endpoint accepts multipart
 * `audio/wav` and either returns `{ enrolled_at }` on success or the
 * standard error envelope `{ error_code, message }` on 4xx/5xx; consumers
 * are expected to call `localizedErrorMessage(error.errorCode, t)` to
 * surface the message in the active locale.
 *
 * Slice-13 / ADR-0029.
 */

export class VoiceEnrollmentApiError extends Error {
  readonly errorCode: string;
  readonly statusCode: number;

  constructor(errorCode: string, message: string, statusCode: number) {
    super(message);
    this.name = "VoiceEnrollmentApiError";
    this.errorCode = errorCode;
    this.statusCode = statusCode;
  }
}

export interface VoiceEnrollmentResponse {
  enrolled_at: string;
}

export interface VoiceEnrollmentStatus {
  /** ISO-8601 timestamp of the latest enrollment, or `null` if the user has
   * never enrolled (or has had their enrollment removed). */
  enrolled_at: string | null;
}

/**
 * Fetch the current user's enrollment status. Used on `/settings/voice` mount
 * so a page reload after a successful enrollment surfaces "已登錄" instead of
 * dropping back to the "開始錄製" idle state.
 */
export async function getVoiceEnrollment(): Promise<VoiceEnrollmentStatus> {
  const response = await fetch("/api/voice_enrollment");
  if (!response.ok) {
    throw new VoiceEnrollmentApiError(
      `http.${response.status}`,
      `Failed to fetch voice enrollment status (HTTP ${response.status})`,
      response.status,
    );
  }
  return (await response.json()) as VoiceEnrollmentStatus;
}

/**
 * Upload a recorded WAV blob to the voice enrollment endpoint.
 *
 * On HTTP 200, returns the response JSON. On any non-2xx status, throws a
 * `VoiceEnrollmentApiError` carrying the error envelope's `error_code` so
 * the caller can resolve a localized message.
 */
export async function uploadVoiceEnrollment(blob: Blob): Promise<VoiceEnrollmentResponse> {
  const form = new FormData();
  // Name the part `sample.wav` so server logs / debugging dumps stay readable;
  // the server identifies the file via the `file` field name, not the filename.
  form.append("file", blob, "sample.wav");

  const response = await fetch("/api/voice_enrollment", {
    method: "POST",
    body: form,
  });

  if (response.ok) {
    return (await response.json()) as VoiceEnrollmentResponse;
  }

  // Non-2xx: try to parse the standard envelope. Some failure modes (network,
  // gateway errors) may not return JSON — fall back to a generic code.
  let errorCode = `http.${response.status}`;
  let message = `Voice enrollment upload failed (HTTP ${response.status})`;
  try {
    const body = (await response.json()) as Partial<{ error_code: string; message: string }>;
    if (typeof body.error_code === "string") {
      errorCode = body.error_code;
    }
    if (typeof body.message === "string" && body.message.length > 0) {
      message = body.message;
    }
  } catch {
    // Body wasn't JSON — keep the generic message.
  }
  throw new VoiceEnrollmentApiError(errorCode, message, response.status);
}
