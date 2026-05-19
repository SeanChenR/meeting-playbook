/**
 * BarVisualizer — ui-overhaul-animated-surfaces task 3.1.
 *
 * Reusable Aura-token bar visualizer (ported pattern from elevenlabs
 * `bar-visualizer`, local extract per spike outcome). Four discrete states:
 *
 *   - `connecting`  — warning-orange bars, slow pulse (≥1.0s cycle)
 *   - `listening`   — speaker-tinted bars, flat low baseline
 *   - `speaking`    — speaker-tinted bars, fast pulse (≤400ms)
 *   - `off`         — muted baseline using `--color-border`, no animation
 *
 * Free of meeting-session domain knowledge so future surfaces (voice-
 * enrollment UI, etc.) can reuse it. Honours `prefers-reduced-motion`
 * via the shared `useReducedMotion` hook — under reduced motion all
 * pulses settle to their listening/off baseline.
 */

import { useReducedMotion } from "../../hooks/use-reduced-motion";
import { cn } from "../../lib/utils";

export type BarVisualizerState = "connecting" | "listening" | "speaking" | "off";
export type BarVisualizerTone = "me" | "them" | "warning";

export interface BarVisualizerProps {
  state: BarVisualizerState;
  tone: BarVisualizerTone;
  barCount?: number;
  ariaLabel: string;
  className?: string;
}

const DEFAULT_BAR_COUNT = 10;

function _toneVar(tone: BarVisualizerTone): string {
  if (tone === "me") return "var(--color-me)";
  if (tone === "them") return "var(--color-them)";
  return "var(--color-warning)";
}

function _barColor(state: BarVisualizerState, tone: BarVisualizerTone): string {
  if (state === "off") return "var(--color-border)";
  if (state === "connecting") return "var(--color-warning)";
  return _toneVar(tone);
}

function _animationName(state: BarVisualizerState, reduced: boolean): string | undefined {
  if (reduced) return undefined;
  if (state === "connecting") return "mp-bv-connect";
  if (state === "speaking") return "mp-bv-speak";
  return undefined;
}

function _baseHeight(state: BarVisualizerState, index: number, count: number): number {
  if (state === "off" || state === "listening") return 3;
  if (state === "connecting") return 6;
  // speaking: deterministic but varied per-bar baseline so the pulse looks
  // organic without random amplitude noise (which broke happy-dom tests).
  const mid = (count - 1) / 2;
  const distance = Math.abs(index - mid);
  return 12 - Math.round(distance * 1.5);
}

export function BarVisualizer({
  state,
  tone,
  barCount = DEFAULT_BAR_COUNT,
  ariaLabel,
  className,
}: BarVisualizerProps) {
  const reduced = useReducedMotion();
  const color = _barColor(state, tone);
  const animation = _animationName(state, reduced);
  const bars = Array.from({ length: barCount });

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      data-state={state}
      data-tone={tone}
      data-reduced-motion={reduced ? "true" : "false"}
      className={cn("inline-flex h-4 items-end gap-0.5", className)}
    >
      {bars.map((_, i) => {
        const height = _baseHeight(state, i, barCount);
        const delay = i * 60;
        return (
          <span
            key={i}
            data-testid="bar-visualizer-bar"
            className="w-0.5 rounded-[1px]"
            style={{
              height: `${height}px`,
              background: color,
              animation: animation
                ? `${animation} ${state === "speaking" ? "380ms" : "1200ms"} ease-in-out ${delay}ms infinite`
                : undefined,
              transformOrigin: "bottom",
            }}
          />
        );
      })}
      <style>{`
        @keyframes mp-bv-connect {
          0%, 100% { opacity: 0.45; transform: scaleY(0.6); }
          50%      { opacity: 1;    transform: scaleY(1.4); }
        }
        @keyframes mp-bv-speak {
          0%, 100% { transform: scaleY(0.6); }
          50%      { transform: scaleY(1.6); }
        }
      `}</style>
    </div>
  );
}
