/**
 * MeetingsList — refactor-meetings-tabs-unified wrapper.
 *
 * Single `/meetings` route. Parses `?view=kanban|calendar` (default
 * `kanban`, unknown values fall back to `kanban`), mounts a shared
 * MeetingsViewTabs row above the panel, and swaps between the Kanban
 * and Calendar panels inside an AnimatePresence boundary with a
 * direction-aware horizontal slide. The tab bar lives outside the
 * boundary so the active-tab pill animates without remounting.
 */

import { useLocation } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useRef } from "react";
import { MeetingsViewTabs, type MeetingsView } from "../../components/meetings-view-tabs";
import { ProtectedShell } from "../../components/protected-shell";
import { MeetingsCalendarPanel } from "./calendar";
import { MeetingsKanbanPanel } from "./kanban-panel";

function _parseView(searchStr: string | undefined): MeetingsView {
  const params = new URLSearchParams(
    (searchStr ?? "").startsWith("?") ? (searchStr ?? "").slice(1) : (searchStr ?? ""),
  );
  return params.get("view") === "calendar" ? "calendar" : "kanban";
}

export function MeetingsList() {
  const location = useLocation();
  const view = useMemo(() => _parseView(location.searchStr ?? ""), [location.searchStr]);
  const reduced = useReducedMotion();

  // Track previous view to drive direction-aware slide.
  const prevViewRef = useRef<MeetingsView>(view);
  const direction = view === prevViewRef.current ? 0 : view === "calendar" ? 1 : -1;
  prevViewRef.current = view;

  const variants = {
    enter: (dir: number) => ({ x: dir * 40, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: number) => ({ x: dir * -40, opacity: 0 }),
  } as const;

  const transition = reduced
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 300, damping: 30 };

  return (
    <ProtectedShell>
      <div className="flex justify-center">
        <MeetingsViewTabs value={view} />
      </div>
      <AnimatePresence mode="wait" custom={direction} initial={false}>
        <motion.div
          key={view}
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={transition}
          data-testid={`meetings-panel-${view}`}
        >
          {view === "calendar" ? <MeetingsCalendarPanel /> : <MeetingsKanbanPanel />}
        </motion.div>
      </AnimatePresence>
    </ProtectedShell>
  );
}
