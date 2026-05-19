/**
 * Popover — radix-ui Popover wrapped with animate-ui motion + Aura tokens.
 * ui-overhaul-primitive-upgrade task 3 (Decision 6: Popover barrel).
 *
 * Used by tag-picker, chunk-action-menu, speaker-color-popover, etc.
 *
 * Motion: opacity + scale from origin defined by data-side; reduced-motion
 * users get instant variants. Backdrop is intentionally absent — popovers
 * are non-modal.
 *
 * Source motif: https://animate-ui.com/docs/components/base/popover (CC0).
 */

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { forwardRef } from "react";
import { cn } from "../../lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;
export const PopoverPortal = PopoverPrimitive.Portal;

export const PopoverContent = forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "center", sideOffset = 6, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 rounded-(--radius-md) border border-(--color-border)",
        "bg-(--color-surface) p-2 text-(--color-foreground) shadow-(--shadow-lg)",
        "origin-(--radix-popover-content-transform-origin)",
        "data-[state=open]:animate-in data-[state=closed]:animate-out",
        "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        "data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1",
        "data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";
