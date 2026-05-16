import { cva, type VariantProps } from "class-variance-authority";
import { type HTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

const alertVariants = cva("relative w-full rounded-md border px-4 py-3 text-sm", {
  variants: {
    variant: {
      default: "border-(--color-border) bg-(--color-card) text-(--color-foreground)",
      destructive:
        "border-(--color-destructive)/30 bg-(--color-destructive)/10 text-(--color-destructive)",
      // Slice-7 round 2: warning = advisory — more visible than `default`,
      // less alarming than `destructive`.
      // Slice-18 follow-up: switch from hard-coded amber-50 / amber-900 to
      // theme-aware oklch tokens so dark mode reads (--color-accent is
      // warm-orange under `--primary-hue-dark: 50`).
      warning: "border-(--color-accent)/40 bg-(--color-accent)/10 text-(--color-foreground)",
      success: "border-(--color-accent)/30 bg-(--color-accent)/10 text-(--color-accent)",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

export type AlertProps = HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>;

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, role = "alert", ...props }, ref) => (
    <div ref={ref} role={role} className={cn(alertVariants({ variant }), className)} {...props} />
  ),
);
Alert.displayName = "Alert";
