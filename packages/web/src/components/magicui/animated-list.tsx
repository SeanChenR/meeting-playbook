/**
 * AnimatedList + AnimatedListItem — ui-overhaul-animated-surfaces task 4.1.
 *
 * Ported from the magicui `animated-list` pattern. Each item enters with
 * `opacity: 0 → 1` + `y: 8 → 0`. Under `prefers-reduced-motion: reduce`
 * the wrapper short-circuits and renders children at their final state
 * (no transition styles applied).
 *
 * Designed for the transcript-pane chunk list, but reusable wherever a
 * stream-style list needs entry animation without per-item bookkeeping.
 */

import { motion } from "framer-motion";
import type { HTMLAttributes, ReactNode } from "react";

import { useReducedMotion } from "../../hooks/use-reduced-motion";

export interface AnimatedListProps extends HTMLAttributes<HTMLElement> {
  as?: "ol" | "ul" | "div";
  children: ReactNode;
}

export function AnimatedList({ as = "ol", children, className, ...rest }: AnimatedListProps) {
  const Tag = as;
  return (
    <Tag className={className} {...rest}>
      {children}
    </Tag>
  );
}

export interface AnimatedListItemProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  /** Stagger delay (seconds) — defaults to 0 (no stagger). */
  delay?: number;
  /** Forward `data-*` attrs and the like through to the underlying <li>. */
  itemProps?: Record<string, unknown>;
}

const ENTER_VARIANTS = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
};

export function AnimatedListItem({
  children,
  className,
  style,
  delay = 0,
  itemProps,
}: AnimatedListItemProps) {
  const reduced = useReducedMotion();
  if (reduced) {
    return (
      <li
        data-testid="animated-list-item"
        data-reduced-motion="true"
        className={className}
        style={style}
        {...(itemProps ?? {})}
      >
        {children}
      </li>
    );
  }
  return (
    <motion.li
      data-testid="animated-list-item"
      data-reduced-motion="false"
      className={className}
      style={style}
      variants={ENTER_VARIANTS}
      initial="initial"
      animate="animate"
      transition={{ duration: 0.22, ease: "easeOut", delay }}
      {...(itemProps ?? {})}
    >
      {children}
    </motion.li>
  );
}
