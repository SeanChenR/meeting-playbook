/**
 * RouteTransition — animate-ui-style page transition wrapper.
 * Slice ui-overhaul-claude-design task 1.6.
 *
 * animate-ui is a Tailwind-native motion library distributed by copy
 * (similar to shadcn / magicui). This is a minimal hand-port providing
 * the cross-fade-on-route-change pattern. Wraps page contents in
 * `AnimatePresence` keyed by the path so React unmounts the outgoing
 * route + mounts the incoming one with opposing fades.
 *
 * Usage (App.tsx, future task):
 *   <RouteTransition path={location.pathname}>
 *     <RouterProvider router={router} />
 *   </RouteTransition>
 */

import { AnimatePresence, motion } from "framer-motion";
import { type ReactNode } from "react";
import { tabContent } from "../../lib/motion-presets";

export interface RouteTransitionProps {
  /** Stable per-route key — usually `location.pathname`. */
  path: string;
  children: ReactNode;
}

export function RouteTransition({ path, children }: RouteTransitionProps) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={path}
        initial="initial"
        animate="animate"
        exit="exit"
        variants={tabContent}
        data-testid="route-transition"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
