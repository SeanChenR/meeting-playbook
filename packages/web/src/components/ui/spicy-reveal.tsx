/**
 * SpicyReveal — ui-overhaul-animated-surfaces task 6.6.
 *
 * Ported from uiverse `spicy-rat-83`. Plays a one-shot reveal animation
 * (clip-path wipe + soft glow) the FIRST time `revealKey` is seen on
 * this device; persists the seen flag under
 * `localStorage["playbookRevealSeen:<revealKey>"]` so re-visits skip
 * the animation. Under `prefers-reduced-motion`, the wrapper renders
 * children at their final state and still persists the seen flag.
 */

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { useReducedMotion } from "../../hooks/use-reduced-motion";
import { cn } from "../../lib/utils";

const STORAGE_PREFIX = "playbookRevealSeen:";

export interface SpicyRevealProps {
  children: ReactNode;
  revealKey: string;
  className?: string;
}

type _PlayedState = "true" | "skipped";

function _readSeen(key: string): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(STORAGE_PREFIX + key) !== null;
  } catch {
    return true;
  }
}

function _writeSeen(key: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + key, "1");
  } catch {
    // Best-effort; if storage is unavailable, the reveal may replay.
  }
}

export function SpicyReveal({ children, revealKey, className }: SpicyRevealProps) {
  const reduced = useReducedMotion();
  const alreadySeen = useMemo(() => _readSeen(revealKey), [revealKey]);
  const [played, setPlayed] = useState<_PlayedState>(alreadySeen ? "skipped" : "true");

  useEffect(() => {
    if (alreadySeen) return;
    _writeSeen(revealKey);
    setPlayed("true");
  }, [alreadySeen, revealKey]);

  const shouldAnimate = !alreadySeen && !reduced;

  return (
    <div
      data-testid="spicy-reveal"
      data-played={played}
      data-reduced-motion={reduced ? "true" : "false"}
      className={cn(
        "relative",
        shouldAnimate ? "animate-[mp-spicy-reveal_520ms_ease-out]" : null,
        className,
      )}
    >
      {children}
      <style>{`
        @keyframes mp-spicy-reveal {
          0%   { clip-path: inset(0 100% 0 0); opacity: 0; filter: blur(4px); }
          60%  { clip-path: inset(0 0 0 0);   opacity: 1; filter: blur(0); }
          100% { clip-path: inset(0 0 0 0);   opacity: 1; filter: blur(0); }
        }
      `}</style>
    </div>
  );
}
