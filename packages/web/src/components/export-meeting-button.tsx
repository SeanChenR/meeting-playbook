/**
 * ExportMeetingButton — slice-22-export-bundle task 4.3.
 *
 * Renders a labelled button on the meeting detail page; clicking triggers
 * the browser-side `<a download>` flow implemented by `exportMeeting`.
 *
 * UI states:
 *  - idle: enabled, label = `t("meetings.detail.export")`.
 *  - in-flight: disabled + spinner-style label = `t("meetings.detail.exporting")`.
 *  - error: button returns to idle; an error toast surfaces the localized
 *    `error_code` (or the `exportFailed` fallback for unknown errors).
 *
 * No emoji per UI conventions; we use a lucide download icon (matches the
 * other action buttons in MetadataCard).
 */

import { Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { exportMeeting } from "../lib/export-api";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MeetingApiError } from "../lib/meetings-api";
import { Button } from "./ui/button";

interface ExportMeetingButtonProps {
  meetingId: string;
  meetingTitle: string;
  scheduledStartAt: string | null;
  /** Optional callback fired after a successful export (refactor task 16.4). */
  onExportSuccess?: () => void;
}

function _asciiSlug(input: string): string {
  // Mirror the backend ascii_slug for the anchor's `download` filename
  // hint. The browser will still honour the server's
  // Content-Disposition if present, but a non-empty hint keeps the
  // download UX consistent in environments where Disposition isn't
  // surfaced (e.g. browser extensions).
  const replaced = input.replace(/[^A-Za-z0-9._-]/g, "_");
  const collapsed = replaced.replace(/_+/g, "_");
  const trimmed = collapsed.replace(/^_+|_+$/g, "").slice(0, 80);
  return trimmed.length === 0 ? "meeting" : trimmed;
}

function _expectedFilename(title: string, scheduledStartAt: string | null): string {
  const dateSource = scheduledStartAt ? new Date(scheduledStartAt) : new Date();
  const isoDate = isNaN(dateSource.getTime())
    ? new Date().toISOString().slice(0, 10)
    : dateSource.toISOString().slice(0, 10);
  return `${_asciiSlug(title)}__${isoDate}.zip`;
}

export function ExportMeetingButton({
  meetingId,
  meetingTitle,
  scheduledStartAt,
  onExportSuccess,
}: ExportMeetingButtonProps) {
  const { t } = useTranslation();
  const [exporting, setExporting] = useState(false);

  const handleClick = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      await exportMeeting(meetingId, _expectedFilename(meetingTitle, scheduledStartAt));
      onExportSuccess?.();
    } catch (err) {
      const fallback = t("meetings.detail.exportFailed");
      let message = fallback;
      if (err instanceof MeetingApiError && err.errorCode) {
        const resolved = localizedErrorMessage(err.errorCode, t);
        // localizedErrorMessage already falls back to errors.common.unknown
        // when the code is unmapped; we still prepend the slice-specific
        // "Export failed" prefix so the user sees the action context.
        message = resolved ? `${fallback}: ${resolved}` : fallback;
      }
      toast.error(message);
    } finally {
      setExporting(false);
    }
  };

  const label = exporting ? t("meetings.detail.exporting") : t("meetings.detail.export");

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      onClick={handleClick}
      disabled={exporting}
      data-testid="export-meeting-button"
    >
      {exporting ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      ) : (
        <Download className="size-3.5" aria-hidden="true" />
      )}
      {label}
    </Button>
  );
}
