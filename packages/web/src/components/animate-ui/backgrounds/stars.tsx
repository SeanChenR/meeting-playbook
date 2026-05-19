/**
 * Stars — ui-overhaul-animated-surfaces task 2.1 + 2.2.
 *
 * Decorative animated stars layer for protected dark-mode shells. Three
 * gates determine whether stars render (per "Stars background SHALL mount
 * only on protected routes in dark mode"):
 *   1. Resolved theme is `dark`
 *   2. `prefers-reduced-motion: reduce` is NOT matched
 *   3. `route` prop is `"protected"` (default). Public routes pass `"public"`.
 * Any gate fail → return null.
 *
 * Star positions are deterministic per mount (seeded by index) so SSR-safe
 * and re-render cheap; opacity flickers via CSS keyframes constrained to
 * `--color-foreground` / `--color-muted-foreground` low-alpha tones.
 * Total star count is bounded at 60 per the spec.
 */

import { useMemo } from "react";

import { useReducedMotion } from "../../../hooks/use-reduced-motion";
import { useTheme } from "../../../lib/theme-provider";

const STAR_COUNT = 60;

export interface StarsProps {
  /** Defaults to "protected"; public routes (login/signup) pass "public". */
  route?: "protected" | "public";
}

interface _Star {
  id: number;
  x: number;
  y: number;
  size: number;
  delay: number;
  duration: number;
  tone: "foreground" | "muted";
}

function _seededStars(count: number): _Star[] {
  const stars: _Star[] = [];
  for (let i = 0; i < count; i++) {
    const x = (i * 137.5) % 100;
    const y = (i * 53.7 + i * i * 0.3) % 100;
    const size = 1 + (i % 3) * 0.5;
    const delay = (i * 0.17) % 5;
    const duration = 3 + (i % 4);
    const tone: _Star["tone"] = i % 5 === 0 ? "foreground" : "muted";
    stars.push({ id: i, x, y, size, delay, duration, tone });
  }
  return stars;
}

export function Stars({ route = "protected" }: StarsProps) {
  const { resolved } = useTheme();
  const reduced = useReducedMotion();
  const stars = useMemo(() => _seededStars(STAR_COUNT), []);

  if (route !== "protected") return null;
  if (resolved !== "dark") return null;
  if (reduced) return null;

  return (
    <div
      aria-hidden
      data-testid="stars-layer"
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      {stars.map((s) => {
        const color =
          s.tone === "foreground" ? "var(--color-foreground)" : "var(--color-muted-foreground)";
        return (
          <span
            key={s.id}
            data-testid="star"
            className="absolute rounded-full"
            style={{
              left: `${s.x}%`,
              top: `${s.y}%`,
              width: `${s.size}px`,
              height: `${s.size}px`,
              background: color,
              opacity: 0.25,
              animation: `mp-star-twinkle ${s.duration}s ease-in-out ${s.delay}s infinite`,
            }}
          />
        );
      })}
      <style>{`
        @keyframes mp-star-twinkle {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 0.55; }
        }
      `}</style>
    </div>
  );
}
