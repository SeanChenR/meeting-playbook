/**
 * MetadataCard — slice ui-overhaul-claude-design task 5.2.
 *
 * Two-column metadata block sitting between the BackLink and the
 * Tabs row on the meeting detail page. Mirrors the design bundle's
 * MetadataCard:
 *
 *   Left column  (flex 1 1 320px)
 *     - status badge (dot) + created/rerun-count meta
 *     - 2xl bold title
 *     - 2-col grid: 對方 / 我方 / 錄音 (each with size-18 Avatar)
 *
 *   Right column (flex 0 0 280px)
 *     - ASR provider Label + Select (hint: "切換下一場會議生效")
 *     - embedded CaptureIndicator
 *
 *   Bottom action row (separated by a divider)
 *     - 開始會議 / 結束會議 (primary or destructive based on phase)
 *     - 重新轉錄
 *     - 匯出 .md (ghost)
 *     - 刪除 (ghost)
 *
 * Behaviour is wired through props supplied by detail.tsx so this stays
 * a presentational component — no React Query / WebSocket coupling here.
 */

import { Mic, Square } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw } from "./animate-ui/icons/refresh-cw";
import { Trash } from "./animate-ui/icons/trash";
import type { MeetingDetail } from "../lib/meetings-api";
import { Avatar } from "./ui/avatar";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Separator } from "./ui/separator";

export interface MetadataCardProps {
  meeting: MeetingDetail;
  /** Slot for the embedded CaptureIndicator (driven by useMeetingSession). */
  captureIndicator: ReactNode;
  /** ASR provider <Select>; passed in so the parent owns the mutation. */
  asrSelector: ReactNode;
  /** Active session phase — flips the start/end button visibility. */
  phase: "idle" | "connecting" | "in_progress" | "ending" | "ended" | "error";
  onStart: () => void;
  onEnd: () => void;
  /** Optional rerun-asr trigger (renders the slot when provided). */
  rerunSlot?: ReactNode;
  /** Destructive delete callback — opens the AlertDialog. */
  onDelete: () => void;
  startDisabled?: boolean;
}

function _statusVariant(status: string): "default" | "success" | "outline" {
  if (status === "in_progress") return "success";
  if (status === "scheduled") return "outline";
  return "default";
}

function _statusColor(status: string): string {
  if (status === "in_progress") return "var(--color-destructive)";
  if (status === "scheduled") return "var(--color-primary)";
  return "var(--color-muted-foreground)";
}

export function MetadataCard({
  meeting,
  captureIndicator,
  asrSelector,
  phase,
  onStart,
  onEnd,
  rerunSlot,
  onDelete,
  startDisabled = false,
}: MetadataCardProps) {
  const { t, i18n } = useTranslation();
  const createdAt = new Date(meeting.created_at).toLocaleString(i18n.language, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const showEndButton = phase === "in_progress";

  return (
    <Card data-testid="meeting-metadata-card">
      <CardContent className="space-y-5 p-5">
        <div className="flex flex-wrap gap-5">
          <div className="min-w-0 flex-[1_1_320px] space-y-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <Badge variant={_statusVariant(meeting.status)} className="gap-1.5">
                <span
                  aria-hidden
                  className="size-1.5 rounded-full"
                  style={{ background: _statusColor(meeting.status) }}
                />
                {t(`meetings.status.${meeting.status}`)}
              </Badge>
              <span className="text-xs text-(--color-muted-foreground)">
                {t("meetings.detail.createdAtLabel")} · {createdAt}
              </span>
            </div>

            <h1
              data-testid="meeting-title"
              className="text-2xl font-bold leading-tight tracking-tight text-(--color-foreground)"
            >
              {meeting.title}
            </h1>

            <dl
              className="grid max-w-[360px] gap-y-1.5 text-sm"
              style={{ gridTemplateColumns: "auto 1fr", columnGap: "14px" }}
            >
              <dt className="text-(--color-muted-foreground)">
                {t("meetings.detail.counterpartyLabel")}
              </dt>
              <dd data-testid="meeting-row-counterparty" className="flex items-center gap-1.5">
                <Avatar
                  alt={meeting.counterparty_display_name}
                  fallback={meeting.counterparty_display_name[0] ?? "?"}
                  className="size-[18px] text-[10px]"
                />
                <span className="font-medium">{meeting.counterparty_display_name}</span>
              </dd>

              <dt className="text-(--color-muted-foreground)">{t("meetings.detail.meLabel")}</dt>
              <dd data-testid="meeting-row-me" className="flex items-center gap-1.5">
                <Avatar
                  alt={meeting.me_display_name}
                  fallback={meeting.me_display_name[0] ?? "?"}
                  className="size-[18px] text-[10px]"
                />
                <span className="font-medium">{meeting.me_display_name}</span>
              </dd>

              <dt className="text-(--color-muted-foreground)">
                {t("meetings.detail.recordingLabel")}
              </dt>
              <dd data-testid="meeting-row-recording" className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className={
                    meeting.recordings_available
                      ? "size-1.5 rounded-full bg-(--color-success)"
                      : "size-1.5 rounded-full bg-(--color-muted-foreground)"
                  }
                />
                <span>
                  {meeting.recordings_available
                    ? t("meetings.detail.recordingAvailable")
                    : t("meetings.detail.recordingExpired")}
                </span>
              </dd>
            </dl>
          </div>

          <div className="flex flex-[0_0_280px] flex-col gap-2.5">
            {asrSelector}
            {captureIndicator}
          </div>
        </div>

        <Separator />

        <div className="flex flex-wrap items-center gap-2">
          {showEndButton ? (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={onEnd}
              data-testid="metadata-end-meeting"
            >
              <Square className="size-3" />
              {t("meetings.session.end")}
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={onStart}
              disabled={startDisabled}
              data-testid="metadata-start-meeting"
            >
              <Mic className="size-3.5" />
              {t("meetings.session.start")}
            </Button>
          )}
          {rerunSlot && <div data-testid="metadata-rerun-slot">{rerunSlot}</div>}
          <div className="flex-1" />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onDelete}
            data-testid="metadata-delete"
          >
            <Trash animateOnHover className="size-3.5" />
            {t("meetings.detail.deleteButton")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// Keep `RefreshCw` re-exported for the parent's rerun button slot
// (callers can compose if they don't want to import lucide directly).
export const _MetadataRefreshIcon = RefreshCw;
