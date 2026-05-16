/**
 * BorderBeam — magicui-inspired rotating gradient border, framer-motion
 * implementation. (Sean's slice-19 settings polish.)
 *
 * Renders an animated conic gradient sized to the parent's box, masked
 * to a 1-2px border ring via a padding-box / border-box exclude mask.
 * Parent must declare `relative` + `overflow-hidden` + `rounded-*`.
 */

import { motion } from "motion/react";
import { cn } from "../../lib/utils";

export interface BorderBeamProps {
  /** Animation duration in seconds. Defaults to 6s for a calm rotation. */
  duration?: number;
  /** Beam length as a fraction of the perimeter (0..1). Default 0.25. */
  size?: number;
  /** Override beam color. Defaults to var(--color-primary). */
  colorVar?: string;
  /** Border thickness in px. Default 2. */
  borderWidth?: number;
  className?: string;
}

export function BorderBeam({
  duration = 6,
  size = 0.25,
  colorVar = "var(--color-primary)",
  borderWidth = 2,
  className,
}: BorderBeamProps) {
  return (
    <motion.span
      aria-hidden
      data-testid="border-beam"
      initial={{ rotate: 0 }}
      animate={{ rotate: 360 }}
      transition={{ duration, repeat: Infinity, ease: "linear" }}
      style={{
        background: `conic-gradient(from 0deg, transparent 0%, ${colorVar} ${size * 100}%, transparent ${(size + 0.01) * 100}%)`,
        padding: `${borderWidth}px`,
        WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
        WebkitMaskComposite: "xor",
        maskComposite: "exclude",
      }}
      className={cn("pointer-events-none absolute inset-0 rounded-[inherit] opacity-70", className)}
    />
  );
}
