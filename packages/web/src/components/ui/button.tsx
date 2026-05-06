import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md",
    "text-sm font-medium leading-none",
    "transition-[background-color,color,border-color,box-shadow,opacity] duration-150",
    "disabled:pointer-events-none disabled:opacity-50",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-(--color-primary) text-(--color-primary-foreground) hover:bg-(--color-primary)/90",
        secondary:
          "bg-(--color-secondary) text-(--color-secondary-foreground) hover:bg-(--color-secondary)/80",
        outline:
          "border border-(--color-border) bg-(--color-card) text-(--color-foreground) hover:bg-(--color-muted)",
        ghost: "text-(--color-foreground) hover:bg-(--color-muted)",
        destructive:
          "bg-(--color-destructive) text-(--color-destructive-foreground) hover:bg-(--color-destructive)/90",
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

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
    );
  },
);
Button.displayName = "Button";
