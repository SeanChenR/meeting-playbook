/**
 * RecordingBadge — slice-11 task 6.1.
 *
 * Coloured dot + localised text indicating whether the meeting still has
 * an on-disk recording (i.e. `recording.deleted_at IS NULL`). Per Sean's
 * UI standards memory: NO emoji — the dot is a Tailwind background-colour
 * span, not a unicode character.
 *
 * `data-state` exists so future CSS / e2e selectors can branch without
 * re-parsing the localised text.
 */

import { useTranslation } from "react-i18next";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

interface RecordingBadgeProps {
  available: boolean;
}

export function RecordingBadge({ available }: RecordingBadgeProps) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2">
      <span className="font-medium">{t("meetings.detail.recordingLabel")}：</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid="recording-badge"
            data-state={available ? "available" : "expired"}
            className="inline-flex items-center gap-1.5 text-sm"
          >
            <span
              aria-hidden
              className={
                available
                  ? "inline-block h-2 w-2 rounded-full bg-(--color-success)"
                  : "inline-block h-2 w-2 rounded-full bg-(--color-muted-foreground)"
              }
            />
            <span>
              {available
                ? t("meetings.detail.recordingAvailable")
                : t("meetings.detail.recordingExpired")}
            </span>
          </span>
        </TooltipTrigger>
        <TooltipContent>{t("ui.tooltip.recording")}</TooltipContent>
      </Tooltip>
    </div>
  );
}
