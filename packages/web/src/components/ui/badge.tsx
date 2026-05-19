import { cva, type VariantProps } from "class-variance-authority";
import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-(--color-muted) text-(--color-muted-foreground)",
        success: "bg-(--color-success)/15 text-(--color-success)",
        warning: "bg-(--color-warning)/15 text-(--color-warning)",
        // Distinct Aura hues for the three lifecycle buckets (driven from
        // MeetingCard's BUCKET_BADGE map). All three pick saturated tints
        // so the kanban columns + cards read instantly different.
        upcoming: "bg-(--color-info)/15 text-(--color-info)",
        completed: "bg-(--color-accent)/15 text-(--color-accent)",
        accent: "bg-(--color-accent)/12 text-(--color-accent)",
        outline: "border border-(--color-border) text-(--color-foreground)",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
