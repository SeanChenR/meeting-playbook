import { type InputHTMLAttributes, forwardRef, useState } from "react";
import { cn } from "../../lib/utils";

export type InputVariant = "default" | "curvy";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Pick between baseline `<input>` and the curvy variant.
   * Default keeps the slice-7 contract exactly. Curvy adds a focus border
   * that sweeps from left → right across the input perimeter; pass `label`
   * to additionally enable the floating-label animation. */
  variant?: InputVariant;
  /** Curvy variant only — label text. When supplied the wrapper renders a
   * floating-label spring; when omitted curvy still applies the sweep
   * border, leaving label ownership to the consumer. */
  label?: string;
}

const _BASE_INPUT_CLS = cn(
  "flex h-10 w-full rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
  "placeholder:text-(--color-muted-foreground)",
  "transition-[border-color,box-shadow] duration-150",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

// Curvy variant uses a slimmer 1px border + suppresses the default
// focus-visible outline (the sweep overlay is the focus affordance).
const _CURVY_INPUT_CLS = cn(
  "flex h-10 w-full rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
  "placeholder:text-(--color-muted-foreground)",
  "transition-[border-color] duration-150 focus:border-transparent",
  "focus-visible:outline-none",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, variant = "default", label, ...props }, ref) => {
    if (variant === "curvy") {
      return <CurvyInput ref={ref} className={className} type={type} label={label} {...props} />;
    }
    return <input type={type} ref={ref} className={cn(_BASE_INPUT_CLS, className)} {...props} />;
  },
);
Input.displayName = "Input";

interface _CurvyInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

const CurvyInput = forwardRef<HTMLInputElement, _CurvyInputProps>(
  ({ className, type, label, onFocus, onBlur, value, defaultValue, ...props }, ref) => {
    const [focused, setFocused] = useState(false);
    // Track uncontrolled value so the floating label reacts to user input
    // without making `value` mandatory. For controlled mode, derive from prop
    // directly so external updates (parent reset, autofill) sync correctly —
    // gemini PR #50 HIGH (input.tsx:44 / :78).
    const [internalValue, setInternalValue] = useState<string>(() =>
      typeof defaultValue === "string" ? defaultValue : "",
    );
    const currentValue = value !== undefined ? String(value) : internalValue;
    const hasValue = currentValue.length > 0;
    const float = focused || hasValue;

    return (
      <div
        data-testid="curvy-wrap"
        data-focused={focused ? "true" : "false"}
        data-floating={float ? "true" : "false"}
        className="relative isolate"
      >
        <input
          ref={ref}
          type={type}
          value={value}
          defaultValue={defaultValue}
          className={cn(
            _CURVY_INPUT_CLS,
            "peer",
            // Reserve top padding only when a floating label is rendered.
            label ? "pt-4" : null,
            className,
          )}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          onChange={(e) => {
            setInternalValue(e.currentTarget.value);
            props.onChange?.(e);
          }}
          {...props}
        />
        {/* Sweep border overlay — fully revealed on focus via clip-path
         * left → right. clip-path is animatable in modern browsers; the
         * fallback under prefers-reduced-motion is an instant reveal. */}
        <span
          aria-hidden
          data-testid="curvy-sweep"
          className={cn(
            "pointer-events-none absolute inset-0 rounded-md border border-(--color-primary)",
            "transition-[clip-path] duration-500 ease-out motion-reduce:transition-none",
          )}
          style={{
            clipPath: focused ? "inset(0 0 0 0)" : "inset(0 100% 0 0)",
          }}
        />
        {label ? (
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
        ) : null}
      </div>
    );
  },
);
CurvyInput.displayName = "CurvyInput";
