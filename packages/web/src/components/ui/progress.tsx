/**
 * Progress (determinate) — ui-overhaul-primitive-upgrade task 5.
 *
 * Bound to Aura tokens: fill = `--color-primary`, track = `--color-surface-2`.
 * Accepts `value` in [0, 100]; clamped. `aria-label` required for AT.
 *
 * Visual layers (top → bottom):
 *   - inner shimmer sweep (mp-shimmer keyframes, motion-reduce safe)
 *   - filled bar (framer width animation)
 *   - track
 *
 * Source motif: https://animate-ui.com/docs/components/base/progress (CC0).
 */

import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/utils";

export interface ProgressProps {
  value: number;
  "aria-label": string;
  className?: string;
  "data-testid"?: string;
}

export function Progress({
  value,
  "aria-label": ariaLabel,
  className,
  "data-testid": dataTestId,
}: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      data-testid={dataTestId}
      className={cn(
        "relative h-2.5 w-full overflow-hidden rounded-(--radius-pill)",
        "bg-(--color-surface-2)",
        className,
      )}
    >
      <motion.div
        className={cn(
          "relative h-full overflow-hidden rounded-(--radius-pill) bg-(--color-primary)",
          // subtle outer glow + inner gradient so the fill reads as alive
          "shadow-[0_0_8px_var(--color-primary)]",
          "before:absolute before:inset-0 before:rounded-(--radius-pill)",
          "before:bg-gradient-to-r before:from-(--color-primary) before:via-(--color-accent) before:to-(--color-primary)",
          "before:opacity-70",
        )}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.35, ease: "easeOut" }}
      >
        {/* Shimmer sweep — animated white-alpha highlight slides across
         * the fill at ~1.4s loop. Skipped under prefers-reduced-motion. */}
        {!prefersReducedMotion && clamped < 100 ? (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 left-0 w-1/3 -skew-x-12 bg-white/30 blur-sm"
            style={{ animation: "mp-progress-shimmer 1.4s linear infinite" }}
          />
        ) : null}
      </motion.div>
    </div>
  );
}
