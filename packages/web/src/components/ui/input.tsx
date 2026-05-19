import { type InputHTMLAttributes, forwardRef, useState } from "react";
import { cn } from "../../lib/utils";

export type InputVariant = "default" | "curvy";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Pick between baseline `<input>` and the ported curvy-earwig-22 variant.
   * Default keeps the slice-7 contract exactly. */
  variant?: InputVariant;
  /** Curvy variant only — label text. The floating motion is driven by the
   * label so a labelless curvy input falls back to default rendering. */
  label?: string;
}

const _BASE_INPUT_CLS = cn(
  "flex h-10 w-full rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
  "placeholder:text-(--color-muted-foreground)",
  "transition-[border-color,box-shadow] duration-150",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, variant = "default", label, ...props }, ref) => {
    if (variant === "curvy" && label) {
      return <CurvyInput ref={ref} className={className} type={type} label={label} {...props} />;
    }
    return <input type={type} ref={ref} className={cn(_BASE_INPUT_CLS, className)} {...props} />;
  },
);
Input.displayName = "Input";

interface _CurvyInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

const CurvyInput = forwardRef<HTMLInputElement, _CurvyInputProps>(
  ({ className, type, label, onFocus, onBlur, value, defaultValue, ...props }, ref) => {
    const [focused, setFocused] = useState(false);
    const [hasValue, setHasValue] = useState(() => {
      if (typeof value === "string") return value.length > 0;
      if (typeof defaultValue === "string") return defaultValue.length > 0;
      return false;
    });
    const float = focused || hasValue;

    return (
      <div
        data-testid="curvy-wrap"
        data-focused={focused ? "true" : "false"}
        data-floating={float ? "true" : "false"}
        className={cn(
          "relative isolate",
          // Aura-token gradient underline that fades in on focus.
          "after:absolute after:bottom-0 after:left-0 after:h-px after:w-full",
          "after:bg-gradient-to-r after:from-(--color-primary) after:via-(--color-accent) after:to-(--color-primary)",
          "after:scale-x-0 after:origin-left after:transition-transform after:duration-200",
          "focus-within:after:scale-x-100 motion-reduce:after:transition-none",
        )}
      >
        <input
          ref={ref}
          type={type}
          value={value}
          defaultValue={defaultValue}
          className={cn(_BASE_INPUT_CLS, "peer pt-4", className)}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          onChange={(e) => {
            setHasValue(e.currentTarget.value.length > 0);
            props.onChange?.(e);
          }}
          {...props}
        />
        <span
          data-testid="curvy-label"
          aria-hidden
          className={cn(
            "pointer-events-none absolute left-3 origin-left text-(--color-muted-foreground)",
            "transition-[transform,color,font-size] duration-200 ease-out",
            "motion-reduce:transition-none",
            float ? "top-1 scale-75 text-(--color-primary)" : "top-1/2 -translate-y-1/2 text-sm",
          )}
        >
          {label}
        </span>
      </div>
    );
  },
);
CurvyInput.displayName = "CurvyInput";
