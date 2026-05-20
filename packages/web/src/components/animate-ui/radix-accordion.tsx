/**
 * Radix Accordion with framer-motion height animation — animate-ui style.
 *
 * Copy-paste pattern (no external animate-ui package): combines
 * `@radix-ui/react-accordion` for a11y + state with `framer-motion` AnimatePresence
 * for smooth open/close height animation. Used by playbook-pane for the 6
 * collapsible field rows.
 */

import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown } from "lucide-react";
import { forwardRef, type ComponentProps } from "react";
import { cn } from "../../lib/utils";

export const Accordion = AccordionPrimitive.Root;

export const AccordionItem = forwardRef<
  HTMLDivElement,
  ComponentProps<typeof AccordionPrimitive.Item>
>(({ className, ...props }, ref) => (
  <AccordionPrimitive.Item
    ref={ref}
    className={cn("border-b border-(--color-border) last:border-b-0", className)}
    {...props}
  />
));
AccordionItem.displayName = "AccordionItem";

export const AccordionTrigger = forwardRef<
  HTMLButtonElement,
  ComponentProps<typeof AccordionPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <AccordionPrimitive.Header className="flex">
    <AccordionPrimitive.Trigger
      ref={ref}
      className={cn(
        "group flex flex-1 items-center justify-between gap-2 py-3 text-left text-sm font-medium",
        "text-(--color-foreground) hover:text-(--color-primary)",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring) focus-visible:ring-offset-2",
        "transition-colors",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronDown
        aria-hidden
        className={cn(
          "size-4 shrink-0 text-(--color-muted-foreground)",
          "transition-transform duration-200",
          "group-data-[state=open]:rotate-180",
        )}
        strokeWidth={1.5}
      />
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
));
AccordionTrigger.displayName = "AccordionTrigger";

export const AccordionContent = forwardRef<
  HTMLDivElement,
  ComponentProps<typeof AccordionPrimitive.Content>
>(({ className, children, ...props }, ref) => {
  const reduced = useReducedMotion();
  return (
    <AccordionPrimitive.Content ref={ref} forceMount {...props} asChild>
      <AnimatePresence initial={false}>
        <motion.div
          key="content"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={reduced ? { duration: 0 } : { duration: 0.22, ease: "easeOut" }}
          className="overflow-hidden text-sm text-(--color-foreground)/85"
        >
          <div className={cn("pb-3 pt-1", className)}>{children}</div>
        </motion.div>
      </AnimatePresence>
    </AccordionPrimitive.Content>
  );
});
AccordionContent.displayName = "AccordionContent";
