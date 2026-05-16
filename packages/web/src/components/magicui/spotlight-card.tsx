/**
 * SpotlightCard — reactbits-inspired mouse-follow radial spotlight.
 *
 * Mouse position is tracked on the container and projected into a radial
 * gradient overlay that fades in on `mouseenter`, follows the pointer,
 * and fades out on `mouseleave`. The overlay sits above the card body
 * but below interactive children (pointer-events-none).
 *
 * The container is `relative` + `overflow-hidden` so the spotlight is
 * clipped by the card's rounded corners.
 */

import { useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface SpotlightCardProps {
  /** Radial gradient inner color. Defaults to var(--color-primary). */
  spotlightColor?: string;
  /** Peak opacity of the spotlight overlay (0..1). Default 0.55. */
  intensity?: number;
  /** Spotlight radius in px. Default 360. */
  radius?: number;
  className?: string;
  children: ReactNode;
}

export function SpotlightCard({
  spotlightColor = "var(--color-primary)",
  intensity = 0.55,
  radius = 360,
  className,
  children,
}: SpotlightCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [opacity, setOpacity] = useState(0);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  function _move(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  return (
    <div
      ref={ref}
      data-testid="spotlight-card"
      onMouseMove={_move}
      onMouseEnter={() => setOpacity(intensity)}
      onMouseLeave={() => setOpacity(0)}
      className={cn("relative overflow-hidden", className)}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] transition-opacity duration-300"
        style={
          {
            opacity,
            background: `radial-gradient(${radius}px circle at ${pos.x}px ${pos.y}px, ${spotlightColor}, transparent 55%)`,
          } as CSSProperties
        }
      />
      {children}
    </div>
  );
}
