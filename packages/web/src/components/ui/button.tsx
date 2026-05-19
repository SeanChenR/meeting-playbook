import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

export const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md",
    "text-sm font-medium leading-none cursor-pointer select-none",
    // Sean review round 5: amp the button hover language. Every variant
    // gets lift + brightness pump + tinted shadow on hover and a
    // press-down on click. Variant blocks layer their own ring / bg /
    // border / text shifts on top. Disabled controls bypass all of it.
    "transition-[background-color,color,border-color,box-shadow,opacity,transform,filter] duration-150",
    "hover:-translate-y-0.5 hover:shadow-lg hover:brightness-110",
    "active:translate-y-0 active:scale-[0.98] active:shadow-sm active:brightness-95",
    "disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-50",
    "disabled:hover:translate-y-0 disabled:hover:shadow-none disabled:hover:brightness-100",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-(--color-primary) text-(--color-primary-foreground) " +
          // Glow shadow + soft ring on hover → primary CTA "pops".
          "hover:shadow-(--color-primary)/40 hover:ring-2 hover:ring-(--color-primary)/40 " +
          "hover:ring-offset-2 hover:ring-offset-(--color-background)",
        secondary:
          "bg-(--color-secondary) text-(--color-secondary-foreground) " +
          "hover:bg-(--color-secondary)/85 hover:ring-1 hover:ring-(--color-border)",
        outline:
          // Outline → filled-on-hover: bg picks up a primary tint, border
          // + text both shift to primary so the button looks like a
          // different (more decisive) state.
          "border border-(--color-border) bg-(--color-card) text-(--color-foreground) " +
          "hover:border-(--color-primary) hover:bg-(--color-primary)/12 hover:text-(--color-primary)",
        ghost:
          // Ghost: previously transparent — now picks up a primary-tinted
          // bg + text colour on hover so it feels clickable.
          "text-(--color-foreground) " +
          "hover:bg-(--color-primary)/12 hover:text-(--color-primary)",
        destructive:
          "bg-(--color-destructive) text-(--color-destructive-foreground) " +
          "hover:shadow-(--color-destructive)/40 hover:ring-2 " +
          "hover:ring-(--color-destructive)/40 hover:ring-offset-2 " +
          "hover:ring-offset-(--color-background)",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 px-3",
        lg: "h-11 px-6",
        icon: "size-10",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

// ui-overhaul-animated-surfaces task 6.3: pink-chicken-70 sweep on hover
// for primary CTAs. Triggered via `data-cta="primary"` so the existing
// `<Button>` API doesn't grow another variant. Motion only; colors stay
// Aura purple. Disabled buttons inherit the pointer-events-none + 0.5
// opacity from the base cva block so the sweep never engages.
const _CTA_SWEEP_CLS =
  "mp-cta-sweep relative isolate overflow-hidden " +
  "before:pointer-events-none before:absolute before:inset-0 before:-translate-x-full " +
  "before:bg-gradient-to-r before:from-transparent before:via-(--color-primary-foreground)/20 before:to-transparent " +
  "before:transition-transform before:duration-500 before:ease-out " +
  "hover:before:translate-x-full motion-reduce:before:transition-none motion-reduce:hover:before:translate-x-full";

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    const isPrimaryCta = (props as Record<string, unknown>)["data-cta"] === "primary";
    return (
      <button
        ref={ref}
        className={cn(
          buttonVariants({ variant, size, className }),
          isPrimaryCta ? _CTA_SWEEP_CLS : null,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
