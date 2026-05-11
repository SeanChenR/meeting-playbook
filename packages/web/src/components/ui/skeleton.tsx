/**
 * Skeleton — pure-CSS shimmer placeholder for loading states.
 * Slice ui-overhaul-claude-design task 1.3.
 *
 * Uses the `mp-shimmer` keyframe defined in index.css; no JS animation.
 * Reduced-motion users see the gradient mid-state (no animation), which is
 * still semantically a placeholder so accessibility is preserved.
 */

import { type HTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

export const Skeleton = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    const testId = (props as Record<string, unknown>)["data-testid"];
    return (
      <div
        ref={ref}
        data-testid={typeof testId === "string" ? testId : "skeleton"}
        className={cn(
          "rounded-md bg-gradient-to-r from-(--color-muted) via-(--color-muted)/60 to-(--color-muted)",
          "motion-safe:bg-[length:200%_100%] motion-safe:animate-[mp-shimmer_1.6s_ease-in-out_infinite]",
          className,
        )}
        {...props}
      />
    );
  },
);
Skeleton.displayName = "Skeleton";
