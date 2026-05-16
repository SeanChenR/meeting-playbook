/**
 * Voice enrollment standalone route — slice-13 / ADR-0029.
 *
 * Standalone for now (per the slice's task 7.1) so it can ship before the
 * `/settings` shell exists; when the shell lands, this component slots in
 * as a sub-page without changes to the recorder logic.
 *
 * Behaviour (verified by `voice.test.tsx`):
 * - Start / Stop recording via `MediaRecorder`, 30-second hard cap.
 * - Live RMS-derived level meter (test-id `voice-level-meter`).
 * - Preview `<audio>` element + Re-record + Save once a sample exists.
 * - Save POSTs to `/api/voice_enrollment` via `uploadVoiceEnrollment`;
 *   localized error messages on 4xx via `localizedErrorMessage`.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

// Slice-19: ProtectedShell now provided by `<SettingsLayout />` parent; the
// page renders content only so the sub-nav doesn't unmount on tab switch.
import { Mic } from "lucide-react";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";
import { Button } from "../../components/ui/button";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  VoiceEnrollmentApiError,
  getVoiceEnrollment,
  uploadVoiceEnrollment,
} from "../../lib/voice-enrollment-api";
import { encodeWavFromBlob } from "../../lib/wav-encoder";

const _MAX_RECORD_SECONDS = 30;

/**
 * Browser-specific MIME negotiation for `MediaRecorder`:
 * - Chrome / Firefox: `audio/webm` (Opus).
 * - Safari (macOS + iOS): no WebM support — falls back to `audio/mp4` (AAC).
 *
 * Returns `null` when none of the preferred types are supported; callers
 * then construct `MediaRecorder` without a `mimeType` option and let the
 * browser pick its own default.
 */
function _pickSupportedMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  for (const mime of ["audio/webm", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported?.(mime)) return mime;
  }
  return null;
}

type RecordingState = "idle" | "recording" | "stopped" | "saving" | "saved";

export function SettingsVoice() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<RecordingState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [levelPercent, setLevelPercent] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Slice-13: on mount, query whether the user already has an enrollment.
  // Page reload after a successful save should land in the "已登錄" view
  // rather than dropping back to the idle "開始錄製" UI.
  const queryClient = useQueryClient();
  const enrollmentQuery = useQuery({
    queryKey: ["voice-enrollment"],
    queryFn: getVoiceEnrollment,
    staleTime: 60_000,
  });

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const tickIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Release object URLs + tracks on unmount or when the preview rebuilds.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      _teardownRecorder();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function _teardownRecorder() {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (tickIntervalRef.current !== null) {
      clearInterval(tickIntervalRef.current);
      tickIntervalRef.current = null;
    }
    if (stopTimeoutRef.current !== null) {
      clearTimeout(stopTimeoutRef.current);
      stopTimeoutRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    analyserRef.current = null;
    recorderRef.current = null;
  }

  async function _startRecording() {
    setErrorMessage(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // MediaRecorder cannot output WAV in any browser; record in whichever
      // container the runtime supports — WebM/Opus on Chrome/Firefox,
      // MP4/AAC on Safari — and transcode to 16kHz mono PCM WAV in
      // `_saveRecording` via `encodeWavFromBlob` before upload.
      const mimeType = _pickSupportedMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream); // last-resort: let the browser pick
      recorderRef.current = recorder;
      const chunks: BlobPart[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        // Preserve the recorder's native MIME so the preview <audio> element
        // can play it back. WAV conversion happens at save time.
        const recordedBlob = new Blob(chunks, {
          type: recorder.mimeType || mimeType || "audio/webm",
        });
        setBlob(recordedBlob);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(recordedBlob));
        setState("stopped");
        _teardownRecorder();
      };

      // Live RMS meter using AudioContext + AnalyserNode.
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      const buffer = new Uint8Array(analyser.frequencyBinCount);

      function _tickLevel() {
        if (!analyserRef.current) return;
        analyserRef.current.getByteTimeDomainData(buffer);
        // Compute RMS in [0, 128] and map to a 0–100 percentage.
        let sum = 0;
        for (const sample of buffer) {
          const centered = sample - 128;
          sum += centered * centered;
        }
        const rms = Math.sqrt(sum / buffer.length);
        setLevelPercent(Math.min(100, Math.round((rms / 64) * 100)));
        rafRef.current = requestAnimationFrame(_tickLevel);
      }
      rafRef.current = requestAnimationFrame(_tickLevel);

      // 1-second tick for the elapsed counter shown to the user.
      setElapsedSeconds(0);
      tickIntervalRef.current = setInterval(() => {
        setElapsedSeconds((s) => s + 1);
      }, 1000);

      // Hard 30-second cutoff — stop the recorder if the user lingers.
      stopTimeoutRef.current = setTimeout(() => {
        if (recorderRef.current && recorderRef.current.state === "recording") {
          recorderRef.current.stop();
        }
      }, _MAX_RECORD_SECONDS * 1000);

      recorder.start();
      setState("recording");
    } catch {
      setErrorMessage(t("settings.voice.permissionDenied"));
    }
  }

  function _stopRecording() {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
    }
  }

  function _resetForRerecord() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setBlob(null);
    setState("idle");
    setElapsedSeconds(0);
    setErrorMessage(null);
  }

  async function _saveRecording() {
    if (!blob) {
      setErrorMessage(t("settings.voice.missingRecording"));
      return;
    }
    setErrorMessage(null);
    setState("saving");
    try {
      // Transcode the recorder's WebM/MP4 output to 16kHz mono PCM WAV
      // before upload — the backend feeds the file straight into pyannote
      // which only reads WAV.
      const wavBlob = await encodeWavFromBlob(blob);
      await uploadVoiceEnrollment(wavBlob);
      // Refresh the enrollment-status query so the "previously enrolled"
      // banner reflects the newly saved row immediately (also makes a
      // page reload after this point land in the right state).
      await queryClient.invalidateQueries({ queryKey: ["voice-enrollment"] });
      setState("saved");
    } catch (err) {
      if (err instanceof VoiceEnrollmentApiError) {
        setErrorMessage(localizedErrorMessage(err.errorCode, t));
      } else {
        setErrorMessage(t("errors.common.unknown"));
      }
      // Stay in "stopped" so the user can retry without re-recording.
      setState("stopped");
    }
  }

  const isRecording = state === "recording";
  const hasPreview = state === "stopped" || state === "saving" || state === "saved";
  // The user is "previously enrolled" only when they have NOT started a new
  // recording yet AND the backend reports a row. Once `state` leaves idle,
  // the freshly-recorded UI takes over.
  const previouslyEnrolledAt =
    state === "idle" ? (enrollmentQuery.data?.enrolled_at ?? null) : null;
  const hasPreviousEnrollment = previouslyEnrolledAt !== null;
  const formattedEnrolledAt = previouslyEnrolledAt
    ? new Date(previouslyEnrolledAt).toLocaleString(i18n.language, {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <GradientCardFrame
      data-testid="settings-voice-card"
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
    >
      <div className="flex flex-col items-center rounded-[inherit] p-8">
        <div className="flex flex-col items-center gap-3 pb-6 text-center">
          <div className="flex size-20 items-center justify-center rounded-full bg-(--color-primary)/15 ring-2 ring-(--color-primary)/40">
            <Mic
              className={
                isRecording
                  ? "size-10 animate-pulse text-(--color-primary)"
                  : "size-10 text-(--color-primary)"
              }
              aria-hidden
            />
          </div>
          <h1
            className="text-xl font-semibold tracking-tight text-(--color-foreground)"
            data-testid="settings-voice-heading"
          >
            {t("settings.voice.heading")}
          </h1>
          <p className="max-w-md text-sm text-(--color-muted-foreground)">
            {t("settings.voice.subhead")}
          </p>
        </div>

        <section className="space-y-4 rounded-md border border-(--color-border)/60 bg-(--color-card)/50 p-6">
          <p className="text-xs text-(--color-muted-foreground)">
            {t("settings.voice.permissionHint")}
          </p>

          {hasPreviousEnrollment && formattedEnrolledAt && (
            <p
              data-testid="voice-previous-enrollment"
              className="rounded-md border border-(--color-success)/40 bg-(--color-success)/10 px-3 py-2 text-sm text-(--color-foreground)"
            >
              {t("settings.voice.previouslyEnrolled", { timestamp: formattedEnrolledAt })}
            </p>
          )}

          {isRecording && (
            <div className="space-y-2" data-testid="voice-level-meter">
              <p className="text-sm text-(--color-foreground)">
                {t("settings.voice.recording", { seconds: elapsedSeconds })}
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-(--color-muted)">
                <div
                  className="h-full bg-(--color-primary) transition-[width] duration-100"
                  style={{ width: `${levelPercent}%` }}
                  data-testid="voice-level-bar"
                />
              </div>
            </div>
          )}

          {hasPreview && previewUrl && (
            <audio controls src={previewUrl} data-testid="voice-preview" className="w-full" />
          )}

          <div className="flex flex-wrap gap-2">
            {state === "idle" && (
              <Button type="button" onClick={_startRecording} data-testid="voice-start-button">
                {hasPreviousEnrollment
                  ? t("settings.voice.reRecordToOverwrite")
                  : t("settings.voice.startRecording")}
              </Button>
            )}
            {isRecording && (
              <Button
                type="button"
                variant="secondary"
                onClick={_stopRecording}
                data-testid="voice-stop-button"
              >
                {t("settings.voice.stopRecording")}
              </Button>
            )}
            {hasPreview && (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={_resetForRerecord}
                  data-testid="voice-rerecord-button"
                >
                  {t("settings.voice.rerecord")}
                </Button>
                <Button
                  type="button"
                  onClick={_saveRecording}
                  disabled={state === "saving"}
                  data-testid="voice-save-button"
                >
                  {state === "saving"
                    ? t("settings.voice.saving")
                    : state === "saved"
                      ? t("settings.voice.saved")
                      : t("settings.voice.save")}
                </Button>
              </>
            )}
          </div>

          {errorMessage && (
            <p
              role="alert"
              data-testid="voice-error"
              className="text-sm text-(--color-destructive)"
            >
              {errorMessage}
            </p>
          )}
          {state === "saved" && (
            <p
              role="status"
              data-testid="voice-saved-confirmation"
              className="text-sm text-(--color-success)"
            >
              {t("settings.voice.saved")}
            </p>
          )}
        </section>
      </div>
    </GradientCardFrame>
  );
}
