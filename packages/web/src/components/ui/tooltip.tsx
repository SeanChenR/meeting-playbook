/**
 * Tooltip — radix-ui-react-tooltip + animate-ui motion + Aura inverse tokens.
 * ui-overhaul-primitive-upgrade task 4 (Decision 7: hover-info audit).
 *
 * Inverse colour pattern: background = `--color-foreground`, text =
 * `--color-background` — gives the tooltip a "chip-on-page" feel rather
 * than blending into a surface card.
 *
 * Source motif: https://animate-ui.com/docs/primitives/animate/tooltip (CC0).
 */

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { forwardRef, type ReactNode } from "react";
import { cn } from "../../lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;

/**
 * Tooltip — auto-wraps a Provider so callsites can stay terse:
 *   <Tooltip><TooltipTrigger ... /><TooltipContent ... /></Tooltip>
 * Nesting under a higher-level `TooltipProvider` (e.g. App-level) is still
 * supported; radix Provider nesting lets the inner one inherit / override.
 */
export function Tooltip({
  delayDuration = 200,
  children,
  ...props
}: TooltipPrimitive.TooltipProps & { children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={delayDuration}>
      <TooltipPrimitive.Root {...props}>{children}</TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-(--radius-sm) border border-(--color-border-strong)",
        "bg-(--color-foreground) px-2.5 py-1.5 text-xs text-(--color-background) shadow-(--shadow-md)",
        "data-[state=delayed-open]:animate-[mp-pop-in_140ms_cubic-bezier(0.16,1,0.3,1)]",
        "data-[state=closed]:animate-[mp-pop-out_100ms_ease-in]",
        "motion-reduce:animate-none",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";
