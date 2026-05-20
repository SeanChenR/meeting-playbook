/**
 * ShineBorder — magicui-inspired animated gradient border.
 *
 * Renders a multi-colour radial gradient masked to a thin ring around the
 * parent box. The gradient slowly drifts across a 300% background area so
 * the colours appear to "shine" along the border without rotating like the
 * earlier `BorderBeam` beam (which Sean found too obvious).
 *
 * Usage: parent must be `relative overflow-hidden rounded-*`. Drop a single
 * <ShineBorder /> as a sibling to the content.
 *
 *   <div className="relative overflow-hidden rounded-2xl ...">
 *     <ShineBorder />
 *     <div className="relative z-[1]">...content...</div>
 *   </div>
 */

import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/utils";

export interface ShineBorderProps {
  /** Border thickness in px. Default 1.5 — slightly hairline. */
  borderWidth?: number;
  /** Animation cycle length in seconds. Default 14 (calm). */
  duration?: number;
  /** Gradient stops. Three Aura tokens by default; pass custom colours
   *  (CSS values) to brand a specific container. */
  colors?: ReadonlyArray<string>;
  className?: string;
}

const _DEFAULT_COLORS: ReadonlyArray<string> = [
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-info)",
];

export function ShineBorder({
  borderWidth = 1.5,
  duration = 14,
  colors = _DEFAULT_COLORS,
  className,
}: ShineBorderProps) {
  const reduced = useReducedMotion();
  const stopList = colors.join(", ");
  const backgroundImage = `radial-gradient(circle at 50% 50%, transparent 0%, ${stopList}, transparent 100%)`;

  return (
    <motion.span
      aria-hidden
      data-testid="shine-border"
      initial={false}
      animate={
        reduced
          ? undefined
          : {
              backgroundPosition: ["0% 0%", "100% 50%", "0% 100%", "50% 0%", "0% 0%"],
            }
      }
      transition={reduced ? { duration: 0 } : { duration, repeat: Infinity, ease: "linear" }}
      style={{
        backgroundImage,
        backgroundSize: "300% 300%",
        padding: `${borderWidth}px`,
        WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
        WebkitMaskComposite: "xor",
        maskComposite: "exclude",
      }}
      data-shine-border
      className={cn(
        // Restrained by default — at 0.9 the gradient read as gaudy on the
        // bone-white light surface. `index.css` bumps `[data-shine-border]`
        // opacity back up in dark mode where the contrast is naturally
        // softer and the colours look at home.
        "pointer-events-none absolute inset-0 rounded-[inherit] opacity-35",
        className,
      )}
    />
  );
}
