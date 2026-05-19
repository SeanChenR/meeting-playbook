/**
 * Loading (indeterminate) — ui-overhaul-primitive-upgrade task 6.
 *
 * Ported from uiverse `gustavofusco/rare-pug-90` (CC0, public domain).
 * Source: https://uiverse.io/gustavofusco/rare-pug-90
 *
 * Three pulsing dots in Aura `--color-primary`. Sizes: sm 6px, md 8px, lg 12px.
 * `prefers-reduced-motion` users see static (non-animating) dots.
 *
 * Keyframes live in index.css under `@keyframes mp-loading-pulse`.
 */

import { cn } from "../../lib/utils";

export interface LoadingProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  "aria-label": string;
}

const _SIZE_PX: Record<NonNullable<LoadingProps["size"]>, string> = {
  sm: "size-1.5",
  md: "size-2",
  lg: "size-3",
};

const _GAP: Record<NonNullable<LoadingProps["size"]>, string> = {
  sm: "gap-1",
  md: "gap-1.5",
  lg: "gap-2",
};

export function Loading({ size = "md", className, "aria-label": ariaLabel }: LoadingProps) {
  const dotClass = _SIZE_PX[size];
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      data-testid="loading"
      className={cn("mp-loading inline-flex items-center", _GAP[size], className)}
    >
      <span
        className={cn("mp-loading-dot rounded-full bg-(--color-primary)", dotClass)}
        style={{ animationDelay: "0ms" }}
      />
      <span
        className={cn("mp-loading-dot rounded-full bg-(--color-primary)", dotClass)}
        style={{ animationDelay: "160ms" }}
      />
      <span
        className={cn("mp-loading-dot rounded-full bg-(--color-primary)", dotClass)}
        style={{ animationDelay: "320ms" }}
      />
    </div>
  );
}
