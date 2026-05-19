/**
 * Progress (determinate) — ui-overhaul-primitive-upgrade task 5.
 *
 * Bound to Aura tokens: fill = `--color-primary`, track = `--color-surface-2`.
 * Accepts `value` in [0, 100]; clamped. `aria-label` required for AT.
 *
 * Source motif: https://animate-ui.com/docs/components/base/progress (CC0).
 */

import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/utils";

export interface ProgressProps {
  value: number;
  "aria-label": string;
  className?: string;
}

export function Progress({ value, "aria-label": ariaLabel, className }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-(--radius-pill) bg-(--color-surface-2)",
        className,
      )}
    >
      <motion.div
        className="h-full rounded-(--radius-pill) bg-(--color-primary)"
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.3, ease: "easeOut" }}
      />
    </div>
  );
}
