import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "flex h-10 w-full rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
          "placeholder:text-(--color-muted-foreground)",
          "transition-[border-color,box-shadow] duration-150",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";
