/**
 * Tooltip — radix-ui-react-tooltip wrapper styled with project tokens.
 * Slice ui-overhaul-claude-design task 1.3.
 *
 * Used by RecordingBadge dot, CaptureIndicator status icons, etc.
 * `TooltipProvider` SHOULD wrap the whole app once (in ProtectedShell /
 * AuthShell) so individual callsites just use Tooltip / TooltipTrigger /
 * TooltipContent.
 */

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { forwardRef } from "react";
import { cn } from "../../lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
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
        "z-50 overflow-hidden rounded-md border border-(--color-border)",
        "bg-(--color-card) px-2.5 py-1.5 text-xs text-(--color-foreground) shadow-md",
        "data-[state=delayed-open]:animate-in data-[state=closed]:animate-out",
        "data-[state=closed]:fade-out-0 data-[state=delayed-open]:fade-in-0",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";
