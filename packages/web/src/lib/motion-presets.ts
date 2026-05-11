/**
 * motion-presets — slice ui-overhaul-claude-design task 1.5.
 *
 * Per `ui-design-system` spec requirement
 * "Animation library usage SHALL follow the framer-motion / magicui /
 * animate-ui split", these presets are the SINGLE source of framer-motion
 * Variants used across the app. Components MUST import from here instead
 * of declaring inline Variants — the preset names show up in spec
 * scenarios so renaming is a spec change, not a code-level refactor.
 *
 * Reduced-motion: framer-motion's `useReducedMotion()` hook reads the
 * media query natively. Components honour it by either skipping the
 * `motion.*` wrapper or passing `transition={{ duration: 0 }}` when the
 * hook returns true. Presets here describe the "motion on" path; the "off"
 * path is the component's responsibility.
 */

import type { Transition, Variants } from "framer-motion";

/** Pane / card entry: subtle 4px upward translate + opacity fade. */
export const paneEnter: Variants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.18, ease: "easeOut" } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.12, ease: "easeIn" } },
};

/** Stagger children by 80ms — applied to a parent motion.div wrapping
 *  multiple paneEnter children (e.g. workspace 3-pane grid). */
export const paneStagger: Transition = { staggerChildren: 0.08 };

/** Tab content cross-fade. Used by Detail page Workspace ↔ Summary swap. */
export const tabContent: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.15, ease: "easeOut" } },
  exit: { opacity: 0, transition: { duration: 0.1, ease: "easeIn" } },
};

/** Modal / dialog scale + fade. Used for AlertDialog, Sheet, etc. */
export const modalScale: Variants = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1, transition: { duration: 0.16, ease: "easeOut" } },
  exit: { opacity: 0, scale: 0.96, transition: { duration: 0.12, ease: "easeIn" } },
};

/** Card hover micro-interaction — subtle lift. Spring for natural feel. */
export const cardHover: Variants = {
  rest: { y: 0, boxShadow: "var(--shadow-sm)" },
  hover: {
    y: -1,
    boxShadow: "var(--shadow-md)",
    transition: { type: "spring", stiffness: 500, damping: 30 },
  },
};
