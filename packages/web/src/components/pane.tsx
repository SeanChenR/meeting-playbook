/**
 * Pane — slice ui-overhaul-claude-design Phase 6 shared shell.
 *
 * The three workspace panes (Playbook / Transcript / Advisor) share this
 * outer chrome:
 *   - Rounded surface card with shadow + 1px border
 *   - Sticky header: 3px-tall accent bar + title + optional badge / actions
 *   - Scrollable body that flexes to fill available height
 *
 * Layout-agnostic: the parent (`Workspace`) decides the dimensions; this
 * component just fills 100% height and lets the inner body scroll.
 */

import type { ReactNode } from "react";
import { cn } from "../lib/utils";

export interface PaneProps {
  title: string;
  /** CSS color value used for the 3px header accent bar (e.g. `var(--color-primary)`). */
  accent?: string;
  /** Optional badge / status pill rendered next to the title. */
  badge?: ReactNode;
  /** Right-aligned actions: button group, tabs, etc. */
  actions?: ReactNode;
  children: ReactNode;
  /** Optional override for the testid (defaults to `pane`). */
  "data-testid"?: string;
  className?: string;
  bodyClassName?: string;
}

export function Pane({
  title,
  accent,
  badge,
  actions,
  children,
  className,
  bodyClassName,
  ...rest
}: PaneProps) {
  const testId = rest["data-testid"] ?? "pane";
  return (
    <div
      data-testid={testId}
      className={cn(
        "flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-(--color-border) bg-(--color-card) shadow-sm",
        className,
      )}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-(--color-border) px-3.5 py-2.5">
        {accent && (
          <span
            aria-hidden
            data-testid="pane-accent"
            className="inline-block h-3.5 w-[3px] rounded-sm"
            style={{ background: accent }}
          />
        )}
        <h2
          data-testid="pane-title"
          className="text-sm font-semibold tracking-wide text-(--color-foreground)"
        >
          {title}
        </h2>
        {badge}
        <div className="flex-1" />
        {actions}
      </header>
      <div data-testid="pane-body" className={cn("min-h-0 flex-1 overflow-auto", bodyClassName)}>
        {children}
      </div>
    </div>
  );
}
