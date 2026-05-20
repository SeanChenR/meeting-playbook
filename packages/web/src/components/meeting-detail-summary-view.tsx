/**
 * MeetingDetailSummaryView — two-column summary tab view.
 *
 * Left column: existing <SummaryPane> (Gemini 2.5 Pro markdown summary).
 * Right column: placeholder for the future post-meeting AI chat feature —
 * shows a localised header (摘要對話), a soft icon, "即將推出" placeholder
 * copy, and three non-interactive example prompt chips.
 *
 * The right column issues no network requests; it is a layout slot only.
 */

import { Hourglass, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import { SummaryPane } from "./summary-pane";

export interface MeetingDetailSummaryViewProps {
  meetingId: string;
  meeting: { title: string; created_at: string; status: string };
}

const _EXAMPLE_CHIPS = [
  "「Joyce 那項做完了嗎？」",
  "「對方資安要求摘要」",
  "「下次該準備什麼？」",
] as const;

export function MeetingDetailSummaryView({ meetingId, meeting }: MeetingDetailSummaryViewProps) {
  const { t } = useTranslation();

  // Pre-completion placeholder — Sean's UX feedback: the tab itself is
  // clickable in every phase, but until the meeting completes there is no
  // summary to render, so we surface the locked-state hint inside the
  // panel instead of greying the tab out.
  if (meeting.status !== "completed") {
    return (
      <div
        data-testid="meeting-summary-locked"
        className="flex w-full items-center justify-center rounded-(--radius-md) border border-(--color-border) bg-(--color-surface)/60 px-6 py-16"
        style={{ minHeight: "var(--detail-column-h, calc(100vh - 320px))" }}
      >
        <div className="flex max-w-md flex-col items-center gap-3 text-center">
          <div className="inline-flex size-12 items-center justify-center rounded-full bg-(--color-primary)/10 text-(--color-primary)">
            <Hourglass className="size-5" strokeWidth={1.5} aria-hidden />
          </div>
          <p className="text-base font-medium text-(--color-foreground)">
            {t("meetings.summary.lockedTitle")}
          </p>
          <p className="text-sm text-(--color-muted-foreground)">
            {t("meetings.summary.lockedSubtitle")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="meeting-summary-view"
      className="grid w-full gap-4"
      style={{
        gridTemplateColumns: "1fr 1fr",
        minHeight: "var(--detail-column-h, calc(100vh - 320px))",
      }}
    >
      {/* Left: markdown summary */}
      <section>
        <SummaryPane meetingId={meetingId} meeting={meeting} />
      </section>

      {/* Right: AI chat placeholder slot */}
      <section
        data-testid="meeting-summary-chat-slot"
        className="flex flex-col items-stretch rounded-(--radius-md) border border-(--color-border) bg-(--color-surface) p-6"
      >
        <header className="mb-4 flex items-center gap-2">
          <MessageSquare
            className="size-4 text-(--color-muted-foreground)"
            strokeWidth={1.5}
            aria-hidden
          />
          <h2 className="text-sm font-semibold text-(--color-foreground)">
            {t("meetings.detail.summaryChatSlotTitle")}
          </h2>
        </header>
        <div className="flex flex-1 flex-col items-center justify-center gap-3 py-8 text-center">
          <p className="text-base font-medium text-(--color-foreground)">
            {t("meetings.detail.summaryChatSlotPlaceholder")}
          </p>
          <p className="max-w-sm text-sm text-(--color-muted-foreground)">
            摘要相關問題的 AI 對話功能下個版本上線。
          </p>
          <div
            data-testid="meeting-summary-chat-example-chips"
            className="mt-4 flex flex-wrap justify-center gap-2"
          >
            {_EXAMPLE_CHIPS.map((label) => (
              <span
                key={label}
                className="cursor-default rounded-full bg-(--color-surface-2) px-3 py-1 text-xs text-(--color-muted-foreground)"
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
