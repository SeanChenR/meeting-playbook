/**
 * SuccessResult — ui-overhaul-animated-surfaces task 6.5.
 *
 * Adopted from `ui.devsloka.in`'s success-result pattern. Renders a brief
 * micro-interaction (animated check + caption) using Aura tokens. Reduced
 * motion skips the animation: the final "check" frame appears immediately
 * and `onAnimationComplete` fires on the next tick so consumers can chain
 * subsequent transitions without waiting on motion.
 */

import { Check } from "lucide-react";
import { useEffect } from "react";

import { useReducedMotion } from "../../hooks/use-reduced-motion";
import { cn } from "../../lib/utils";

export interface SuccessResultProps {
  message: string;
  onAnimationComplete?: () => void;
  className?: string;
}

export function SuccessResult({ message, onAnimationComplete, className }: SuccessResultProps) {
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!reduced) return;
    const id = window.setTimeout(() => onAnimationComplete?.(), 0);
    return () => window.clearTimeout(id);
  }, [reduced, onAnimationComplete]);

  return (
    <div
      data-testid="success-result"
      role="status"
      data-reduced-motion={reduced ? "true" : "false"}
      className={cn(
        "inline-flex items-center gap-2 rounded-md bg-(--color-success-soft) px-3 py-2",
        "text-sm text-(--color-foreground)",
        className,
      )}
    >
      <span
        data-testid="success-result-check"
        className={cn(
          "inline-flex size-6 items-center justify-center rounded-full bg-(--color-success)/20",
          "text-(--color-success)",
          reduced ? null : "animate-[mp-success-pop_220ms_ease-out]",
        )}
        onAnimationEnd={reduced ? undefined : onAnimationComplete}
      >
        <Check className="size-4" aria-hidden />
      </span>
      <span>{message}</span>
      <style>{`
        @keyframes mp-success-pop {
          0%   { transform: scale(0.6); opacity: 0; }
          60%  { transform: scale(1.1); opacity: 1; }
          100% { transform: scale(1);   opacity: 1; }
        }
      `}</style>
    </div>
  );
}
