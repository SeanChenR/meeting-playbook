/**
 * GradientCardFrame — composable card shell with a gradient border + a
 * subtle radial background, both of which intensify on hover (Sean
 * review round 4: hover effects should change bg + border, not a
 * mouse-follow spotlight).
 *
 * The border trick uses double-background + padding-box / border-box
 * masks so the border draws a real gradient line without nudging
 * layout. On hover the outer gradient opacity jumps from 40 → 80 and
 * the inner radial brightens, giving a clear "this card is alive"
 * affordance without the noise of a rotating beam or moving spotlight.
 */

import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface GradientCardFrameProps {
  /** Border + radial accent color. Default var(--color-primary). */
  accent?: string;
  /** Border + radial secondary color (for the gradient line). Default var(--color-accent). */
  accentAlt?: string;
  /**
   * When true, all hover affordances are suppressed: no card lift, no
   * brighter border, no brighter radial bg. The static gradient border
   * + subtle radial stay. Dashboard charts pass this — they're read-only
   * surfaces, hover lift was visual noise.
   */
  disableHover?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
  "data-testid"?: string;
}

export function GradientCardFrame({
  accent = "var(--color-primary)",
  accentAlt = "var(--color-accent)",
  disableHover = false,
  className,
  bodyClassName,
  children,
  ...props
}: GradientCardFrameProps) {
  return (
    <div
      data-testid={props["data-testid"]}
      // Outer wrapper draws the gradient border via padding-box / border-box
      // masks. The `group` class lets the inner body react to hover via
      // group-hover utilities (no JS / no re-render).
      className={cn(
        "group relative rounded-xl p-px",
        !disableHover &&
          "transition-[background,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-lg",
        className,
      )}
      style={
        {
          "--card-accent": accent,
          "--card-accent-alt": accentAlt,
          background: `linear-gradient(135deg, ${accent}40, transparent 35%, transparent 65%, ${accentAlt}40)`,
        } as React.CSSProperties
      }
    >
      {!disableHover && (
        // Hover-only overlay: brightens the gradient border by stacking a
        // higher-opacity copy on top, fading in via opacity transition.
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          style={{
            background: `linear-gradient(135deg, ${accent}, transparent 35%, transparent 65%, ${accentAlt})`,
          }}
        />
      )}
      <div
        className={cn(
          "relative rounded-[calc(theme(borderRadius.xl)-1px)]",
          !disableHover && "transition-[background] duration-200",
          bodyClassName,
        )}
        style={{
          background: `radial-gradient(at 100% 0%, color-mix(in oklch, ${accent} 8%, var(--color-card)) 0%, var(--color-card) 60%)`,
        }}
      >
        {!disableHover && (
          // Hover overlay on the body: stronger radial tint that fades in.
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
            style={{
              background: `radial-gradient(at 100% 0%, color-mix(in oklch, ${accent} 18%, var(--color-card)) 0%, var(--color-card) 70%)`,
            }}
          />
        )}
        {/* `h-full` so flex chains in children (e.g. chart cards using
            `flex flex-col` + `flex-1` for the chart body) don't collapse
            when bodyClassName carries `h-full`. */}
        <div className="relative h-full">{children}</div>
      </div>
    </div>
  );
}
