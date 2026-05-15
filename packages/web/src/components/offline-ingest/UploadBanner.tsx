/**
 * Meeting-detail conditional banner for offline audio ingest (slice-14 task 5.3).
 *
 * Render rules (per spec `Meeting detail conditional banner offers upload entry`):
 * - `meeting.status === "scheduled"`
 * - `new Date() > new Date(meeting.scheduled_end_at)`
 * - `meeting.recordings.length === 0`  (proxied via `recordings_available`)
 *
 * When all three hold, the banner exposes an "Upload audio" button. When
 * any condition fails the component returns null so the page layout
 * stays untouched.
 *
 * Dialog open/close state is managed at the parent route level so the
 * banner stays a pure conditional renderer (cheaper to unit test).
 */

import { Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { type MeetingDetail } from "@/lib/meetings-api";

export interface UploadBannerProps {
  meeting: MeetingDetail;
  onUploadClick: () => void;
  /** Override "now" in tests so we can assert past / future cases. */
  now?: Date;
}

export function shouldShowOfflineIngestBanner(
  meeting: MeetingDetail,
  now: Date = new Date(),
): boolean {
  if (meeting.status !== "scheduled") return false;
  if (meeting.recordings_available) return false;
  if (!meeting.scheduled_end_at) return false;
  return now.getTime() > new Date(meeting.scheduled_end_at).getTime();
}

export function UploadBanner({ meeting, onUploadClick, now }: UploadBannerProps) {
  const { t } = useTranslation();

  if (!shouldShowOfflineIngestBanner(meeting, now)) {
    return null;
  }

  return (
    <div
      data-testid="offline-ingest-banner"
      className="rounded-lg border border-(--color-border) bg-(--color-card) p-4 flex items-center justify-between gap-4"
    >
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-(--color-foreground)">
          {t("offline_ingest.banner.heading")}
        </h3>
        <p className="text-xs text-(--color-muted-foreground)">
          {t("offline_ingest.banner.subhead")}
        </p>
      </div>
      <Button onClick={onUploadClick} variant="default" size="sm">
        <Upload className="w-4 h-4 mr-2" />
        {t("offline_ingest.banner.cta")}
      </Button>
    </div>
  );
}
