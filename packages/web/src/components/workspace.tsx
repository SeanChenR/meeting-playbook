/**
 * Workspace — three equal-width columns, always.
 *
 * Refactor v2 (claude-design alignment):
 *   - MeetingColumn is now a pure shell (border + surface + scroll) — it no
 *     longer renders its own header row. The inner <Pane> in each column
 *     provides the single, unified header (accent bar + title + chip +
 *     actions). This removes the duplicate title problem.
 *   - Grid is `1fr 1fr 1fr` (equal width); min-w 300 per column.
 *   - Height derived from CSS var `--detail-column-h` (set by detail.tsx via
 *     ResizeObserver). Fallback raised so the column feels less cramped.
 *   - All three columns therefore share an identical Pane-driven header
 *     height — no need to fight cross-column header alignment manually.
 *
 * The three panes (Playbook / Transcript / Advisor) are passed as children
 * so this component stays presentational; it doesn't fetch or own state.
 */

import { type ReactNode } from "react";
import { cn } from "../lib/utils";

export interface WorkspaceProps {
  playbook: ReactNode;
  transcript: ReactNode;
  advisor: ReactNode;
}

export interface MeetingColumnProps {
  /** Stable identifier — drives `data-testid` so the existing workspace tests
   *  (and DOM-order assertions) keep working without churn. */
  variant: "playbook" | "transcript" | "advisor";
  children: ReactNode;
}

export function MeetingColumn({ variant, children }: MeetingColumnProps) {
  return (
    <section
      data-testid={`meeting-column-${variant}`}
      className={cn(
        "flex min-w-[300px] min-h-0 flex-col",
        "rounded-(--radius-lg) border border-(--color-border) bg-(--color-surface)",
        "shadow-(--shadow-sm) overflow-hidden",
      )}
      style={{ height: "var(--detail-column-h, max(calc(100vh - 180px), 78vh))" }}
    >
      {children}
    </section>
  );
}

export function Workspace({ playbook, transcript, advisor }: WorkspaceProps) {
  return (
    <div data-testid="workspace" className="grid w-full grid-cols-3 gap-4">
      <MeetingColumn variant="playbook">{playbook}</MeetingColumn>
      <MeetingColumn variant="transcript">{transcript}</MeetingColumn>
      <MeetingColumn variant="advisor">{advisor}</MeetingColumn>
    </div>
  );
}
