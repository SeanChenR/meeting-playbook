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
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
  "data-testid"?: string;
}

export function GradientCardFrame({
  accent = "var(--color-primary)",
  accentAlt = "var(--color-accent)",
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
        "group relative rounded-xl p-px transition-[background,box-shadow,transform] duration-200",
        // Lift the whole card and add a soft glow on hover.
        "hover:-translate-y-0.5 hover:shadow-lg",
        className,
      )}
      style={
        {
          // CSS vars expose accent colors to the body's hover state so we
          // don't have to bake them into class strings.
          "--card-accent": accent,
          "--card-accent-alt": accentAlt,
          background: `linear-gradient(135deg, ${accent}40, transparent 35%, transparent 65%, ${accentAlt}40)`,
        } as React.CSSProperties
      }
    >
      {/* Hover-only overlay: brightens the gradient border by stacking a
          higher-opacity copy on top, fading in via opacity transition. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{
          background: `linear-gradient(135deg, ${accent}, transparent 35%, transparent 65%, ${accentAlt})`,
        }}
      />
      <div
        className={cn(
          "relative rounded-[calc(theme(borderRadius.xl)-1px)] transition-[background] duration-200",
          bodyClassName,
        )}
        style={{
          // Subtle radial accent in the top-right corner — uses color-mix
          // so it adapts to the active theme without hard-coded hex. The
          // mix percentage jumps on hover via inline CSS var swap below.
          background: `radial-gradient(at 100% 0%, color-mix(in oklch, ${accent} 8%, var(--color-card)) 0%, var(--color-card) 60%)`,
        }}
      >
        {/* Hover overlay on the body: stronger radial tint that fades in. */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          style={{
            background: `radial-gradient(at 100% 0%, color-mix(in oklch, ${accent} 18%, var(--color-card)) 0%, var(--color-card) 70%)`,
          }}
        />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}
