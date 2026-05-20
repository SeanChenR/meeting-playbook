/**
 * HeadphonesHint — info-style inline alert above the meeting tabs.
 *
 * Visual matches the Claude Design `.alert-info` spec:
 *   - primary-soft background, primary-tinted text + border
 *   - white circular icon bubble (containing headphones lucide icon) on the left
 *   - dismiss `X` icon button on the right (collapses for the current page life)
 *
 * BlackHole's Multi-Output Device routes system audio to BOTH speakers AND
 * BlackHole. In dual ASR mode without headphones, the mic picks up speaker
 * output, so `me.wav` ends up duplicating `counterparty.wav`. This hint is
 * the user-facing mitigation (no DSP echo cancellation in the project).
 */

import { Headphones, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export interface HeadphonesHintProps {
  visible: boolean;
}

export function HeadphonesHint({ visible }: HeadphonesHintProps) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(false);
  if (!visible || dismissed) return null;

  return (
    <div
      data-testid="headphones-hint"
      role="alert"
      className="flex items-center gap-2.5 rounded-(--radius-md) border border-(--color-primary-soft) bg-(--color-primary-soft)/60 px-3 py-2 text-[12.5px] leading-snug text-(--color-foreground)"
    >
      <span className="inline-flex size-[22px] items-center justify-center rounded-full bg-(--color-surface) text-(--color-primary)">
        <Headphones className="size-3.5" strokeWidth={1.5} aria-hidden />
      </span>
      <span className="flex-1">{t("meetings.session.headphonesHint")}</span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        data-testid="headphones-hint-dismiss"
        aria-label="dismiss"
        className="inline-flex size-[22px] items-center justify-center rounded-md text-(--color-muted-foreground) hover:bg-(--color-surface) hover:text-(--color-foreground)"
      >
        <X className="size-3" strokeWidth={1.5} aria-hidden />
      </button>
    </div>
  );
}
