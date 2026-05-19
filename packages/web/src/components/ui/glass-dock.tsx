/**
 * GlassDock — ui-overhaul-animated-surfaces task 5.1 + 5.2.
 *
 * Generic Aura-token glass-dock container (local extract from the
 * vengenceui pattern per spike outcome — vengenceui is not on npm).
 *
 * Visual contract:
 *   - backdrop-blur
 *   - inner border highlight via `--color-border`
 *   - rounded `--radius-lg`
 *   - subtle ambient shadow (token-driven via `shadow-lg`)
 *
 * Does NOT position itself; callers apply `className` for placement
 * (e.g. `fixed bottom-0 inset-x-0`). Used initially to wrap the
 * meeting-audio mini-player chrome (task 5.2).
 *
 * NOTE: GlassDock is a static surface — it schedules no animation, no
 * transition, no requestAnimationFrame loop. The spec's prefers-reduced-
 * motion gate therefore does not apply. The marker below keeps the
 * effect-layer audit aware that this is an intentional no-op (the audit
 * greps for either `useReducedMotion` or `motion-reduce`).
 *
 * motion-reduce: not-applicable (no scheduled motion).
 */

import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/utils";

export interface GlassDockProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function GlassDock({ children, className, ...rest }: GlassDockProps) {
  return (
    <div
      data-testid="glass-dock"
      className={cn(
        // Glass surface: blur + translucent card background.
        "backdrop-blur-md bg-(--color-card)/70",
        // Token-driven border + ambient shadow.
        "border border-(--color-border) shadow-lg",
        // Sharp Aura radius (`--radius-lg` = 8px per P1 token catalogue).
        "rounded-lg",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
