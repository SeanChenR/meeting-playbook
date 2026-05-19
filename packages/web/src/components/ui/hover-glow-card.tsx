/**
 * HoverGlowCard — ui-overhaul-animated-surfaces task 6.1.
 *
 * Port of uiverse `cuddly-catfish-6` (CSS snippet, not on npm). Provides
 * a reusable hover surface: subtle lift + border glow + shadow on hover.
 * All colors via Aura tokens — no raw hex.
 *
 * Two render modes:
 *   - default: wraps `children` in a `<div>`
 *   - `asChild`: clones the single React child and merges the hover-glow
 *     classes onto it (use this when the consumer needs the click surface
 *     to be a `<Link>` / `<a>` / `<button>` to preserve a11y semantics).
 *
 * Honours `prefers-reduced-motion`: under reduce, the lift transform is
 * dropped; only the static border / shadow change on hover remain.
 */

import { Children, cloneElement, isValidElement, type HTMLAttributes, type ReactNode } from "react";

import { useReducedMotion } from "../../hooks/use-reduced-motion";
import { cn } from "../../lib/utils";

const _BASE_CLS =
  "rounded-lg border border-(--color-border) bg-(--color-card) shadow-sm " +
  // Longer + cubic-bezier easing so the lift + glow feels gradual, not a
  // 150ms snap. Border tint at 60% opacity reads more clearly than 40%.
  "transition-[box-shadow,border-color,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] " +
  "hover:border-(--color-primary)/60 hover:shadow-lg";

const _MOTION_CLS = "hover:-translate-y-1 hover:scale-[1.015]";

export interface HoverGlowCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  asChild?: boolean;
}

export function HoverGlowCard({
  children,
  className,
  asChild = false,
  ...rest
}: HoverGlowCardProps) {
  const reduced = useReducedMotion();
  const composed = cn(_BASE_CLS, reduced ? null : _MOTION_CLS, className);
  const dataReduced = reduced ? "true" : "false";

  if (asChild) {
    const only = Children.only(children);
    if (!isValidElement(only)) return null;
    const child = only as React.ReactElement<{ className?: string; [k: string]: unknown }>;
    const childCls = (child.props.className as string | undefined) ?? "";
    const childTestId = (child.props["data-testid"] as string | undefined) ?? "hover-glow-card";
    return cloneElement(child, {
      "data-testid": childTestId,
      "data-hover-glow-card": "true",
      "data-reduced-motion": dataReduced,
      className: cn(composed, childCls),
    });
  }

  return (
    <div
      data-testid="hover-glow-card"
      data-reduced-motion={dataReduced}
      className={composed}
      {...rest}
    >
      {children}
    </div>
  );
}
