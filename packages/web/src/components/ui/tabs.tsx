/**
 * Tabs primitive (slice-10) — shadcn style wrapper over @radix-ui/react-tabs.
 *
 * Used by the meeting detail page to split workspace (3-column session UI)
 * from the post-meeting summary view. Disabled triggers (e.g. summary tab
 * before a meeting completes) render with reduced opacity + cursor-not-allowed
 * via Tailwind data-attribute selectors.
 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { type ComponentProps } from "react";
import { cn } from "../../lib/utils";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-md bg-(--color-muted) p-1 text-(--color-muted-foreground)",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:bg-(--color-background) data-[state=active]:text-(--color-foreground) data-[state=active]:shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn(
        "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className,
      )}
      {...props}
    />
  );
}
