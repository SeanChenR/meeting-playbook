/**
 * useReducedMotion — ui-overhaul-animated-surfaces task 1.1.
 *
 * Single canonical source for `prefers-reduced-motion: reduce`. Every
 * effect-layer component (Stars, AnimatedList, BarVisualizer, GlassDock,
 * HoverGlowCard, SuccessResult, SpicyReveal, curvy Input, primary CTA hover)
 * consults this hook so a runtime preference flip settles in-flight motion.
 */

import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function _initial(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(_initial);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(QUERY);
    const onChange = () => setReduced(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
