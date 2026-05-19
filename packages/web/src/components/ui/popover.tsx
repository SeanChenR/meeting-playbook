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
        // Use real CSS keyframes (defined in index.css) since this project
        // does not ship the tailwindcss-animate plugin that the original
        // `animate-in fade-in-0 zoom-in-95` utilities depend on.
        "data-[state=open]:animate-[mp-pop-in_180ms_cubic-bezier(0.16,1,0.3,1)]",
        "data-[state=closed]:animate-[mp-pop-out_120ms_ease-in]",
        "motion-reduce:animate-none",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";
