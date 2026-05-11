/**
 * Workspace — slice ui-overhaul-claude-design task 5.5.
 *
 * Hosts the three workspace panes (Playbook / Transcript / Advisor) in
 * either a 3-column grid (`columns`) or a 3-row stack (`stack`). Grid
 * templates follow the design bundle:
 *
 *   columns → minmax(260px, 0.8fr) minmax(360px, 1.2fr) minmax(280px, 0.9fr)
 *   stack   → minmax(180px, 0.9fr) minmax(220px, 1.2fr) minmax(180px, 0.9fr)
 *
 * Layout transitions use framer-motion `layout` so the panes morph their
 * geometry instead of jumping; respects `prefers-reduced-motion: reduce`
 * by switching to an instant `transition={{ duration: 0 }}` (no class
 * markers — only motion stylings).
 */

import { motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import type { DetailLayout } from "../hooks/use-detail-layout";

export interface WorkspaceProps {
  layout: DetailLayout;
  playbook: ReactNode;
  transcript: ReactNode;
  advisor: ReactNode;
}

const COLUMNS_TEMPLATE = "minmax(260px, 0.8fr) minmax(360px, 1.2fr) minmax(280px, 0.9fr)";
const STACK_TEMPLATE = "minmax(180px, 0.9fr) minmax(220px, 1.2fr) minmax(180px, 0.9fr)";

function _usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export function Workspace({ layout, playbook, transcript, advisor }: WorkspaceProps) {
  const reduced = _usePrefersReducedMotion();
  const isColumns = layout === "columns";

  // Fixed viewport-bound height so an unbounded transcript doesn't push the
  // page into infinite scroll. ~330px reserves room for NavBar (56) +
  // BackLink (~32) + MetadataCard (~200) + Tabs row (~40) + paddings.
  const gridStyle: React.CSSProperties = isColumns
    ? {
        display: "grid",
        gridTemplateColumns: COLUMNS_TEMPLATE,
        gap: 12,
        height: "calc(100dvh - 330px)",
        minHeight: "480px",
      }
    : {
        display: "grid",
        gridTemplateRows: STACK_TEMPLATE,
        gap: 12,
        height: "calc(100dvh - 330px)",
        minHeight: "640px",
      };

  const transition = reduced
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 340, damping: 36, mass: 0.6 };

  return (
    <div data-testid="workspace" data-layout={layout} style={gridStyle} className="min-h-0">
      <motion.div
        layout
        transition={transition}
        data-testid="workspace-pane-playbook"
        className="min-h-0 min-w-0 overflow-hidden"
      >
        {playbook}
      </motion.div>
      <motion.div
        layout
        transition={transition}
        data-testid="workspace-pane-transcript"
        className="min-h-0 min-w-0 overflow-hidden"
      >
        {transcript}
      </motion.div>
      <motion.div
        layout
        transition={transition}
        data-testid="workspace-pane-advisor"
        className="min-h-0 min-w-0 overflow-hidden"
      >
        {advisor}
      </motion.div>
    </div>
  );
}
