/**
 * CaptureIndicator — small status pill for an active audio capture session.
 *
 * Per slice-06 design: three states map to visual variants.
 * NO emojis (per UI feedback memory). Pulsing dot via Tailwind's
 * `animate-pulse`; replaced in the future UI overhaul.
 */

import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";

export type CaptureState = "idle" | "active" | "silence_warning" | "ending";

interface CaptureIndicatorProps {
  state: CaptureState;
}

export function CaptureIndicator({ state }: CaptureIndicatorProps) {
  const { t } = useTranslation();

  if (state === "idle") return null;

  const isWarning = state === "silence_warning";
  const isEnding = state === "ending";

  const label = isWarning
    ? t("meetings.session.silenceWarning")
    : isEnding
      ? t("meetings.session.endingHint")
      : t("meetings.session.capturing");

  return (
    <div
      data-testid="capture-indicator"
      data-state={state}
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium",
        isWarning
          ? "bg-(--color-destructive)/10 text-(--color-destructive)"
          : isEnding
            ? "bg-(--color-muted) text-(--color-muted-foreground)"
            : "bg-(--color-primary)/10 text-(--color-primary)",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          isWarning
            ? "bg-(--color-destructive)"
            : isEnding
              ? "bg-(--color-muted-foreground) animate-pulse"
              : "bg-(--color-primary) animate-pulse",
        )}
      />
      {label}
    </div>
  );
}
