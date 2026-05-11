/**
 * NumberTicker — magicui-style animated numeric counter.
 * Slice ui-overhaul-claude-design task 1.6.
 *
 * magicui distributes components by copy (no npm package), so this file is
 * a hand-port of the canonical NumberTicker pattern using framer-motion's
 * useMotionValue + useSpring. Used by TranscriptPane re-run overlay
 * (animates `chunks_processed` between polls — see meeting-session spec).
 */

import { useMotionValue, useSpring, useTransform } from "framer-motion";
import { motion } from "framer-motion";
import { useEffect } from "react";

export interface NumberTickerProps {
  /** Target value the ticker animates toward whenever it changes. */
  value: number;
  /** Decimal places to render (default 0 → integer). */
  decimals?: number;
  /** Spring stiffness (higher = snappier). Default 90. */
  stiffness?: number;
  /** Spring damping (higher = less bounce). Default 18. */
  damping?: number;
  className?: string;
}

export function NumberTicker({
  value,
  decimals = 0,
  stiffness = 90,
  damping = 18,
  className,
}: NumberTickerProps) {
  const motionValue = useMotionValue(value);
  const spring = useSpring(motionValue, { stiffness, damping });
  const display = useTransform(spring, (latest) => latest.toFixed(decimals));

  useEffect(() => {
    motionValue.set(value);
  }, [motionValue, value]);

  return (
    <motion.span data-testid="number-ticker" className={className}>
      {display}
    </motion.span>
  );
}
