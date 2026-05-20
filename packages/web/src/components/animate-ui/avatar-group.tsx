/**
 * AvatarGroup — overlapping avatars + optional "+N" chip.
 *
 * animate-ui copy-paste pattern (no external package). Used by MeetingHeaderBar
 * when `counterparty_display_name` parses into 2+ names: shows up to `max`
 * avatars overlapping and collapses the rest into a single `+N` chip.
 */

import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface AvatarGroupProps {
  /** Names parsed from `counterparty_display_name` (one per attendee). */
  names: string[];
  /** Max avatars to render before collapsing into `+N` chip. Default 3. */
  max?: number;
  /** Per-avatar render function. Defaults to a circular initial chip. */
  renderAvatar?: (name: string, index: number) => ReactNode;
  /** Optional className for the outer wrapper. */
  className?: string;
}

function _DefaultAvatar({ name, index }: { name: string; index: number }) {
  const initial = name.trim().slice(0, 1) || "?";
  // Hue rotates per-index so multiple counterparties don't share the same colour.
  const hue = 280 + ((index * 37) % 360);
  return (
    <span
      data-testid="avatar-group-avatar"
      className={cn(
        "inline-flex items-center justify-center rounded-full border-2 border-(--color-surface)",
        "size-6 text-[10px] font-semibold",
      )}
      style={{
        background: `oklch(0.92 0.04 ${hue})`,
        color: `oklch(0.42 0.14 ${hue})`,
      }}
      title={name}
    >
      {initial}
    </span>
  );
}

export function AvatarGroup({ names, max = 3, renderAvatar, className }: AvatarGroupProps) {
  const visible = names.slice(0, max);
  const overflow = Math.max(0, names.length - max);
  return (
    <div className={cn("inline-flex items-center", className)} data-testid="avatar-group">
      <div className="flex -space-x-2">
        {visible.map((n, i) =>
          renderAvatar ? (
            <span key={`${n}-${i}`}>{renderAvatar(n, i)}</span>
          ) : (
            <_DefaultAvatar key={`${n}-${i}`} name={n} index={i} />
          ),
        )}
      </div>
      {overflow > 0 && (
        <span
          data-testid="avatar-group-overflow"
          className={cn(
            "ml-1 inline-flex items-center justify-center rounded-full",
            "bg-(--color-surface-2) text-(--color-muted-foreground)",
            "size-6 text-[10px] font-medium",
          )}
        >
          +{overflow}
        </span>
      )}
    </div>
  );
}

/**
 * Parse a comma / Chinese-comma / ideographic-comma separated string into
 * a trimmed non-empty name array. Whitespace around separators is tolerated.
 */
export function parseCounterpartyNames(s: string | undefined | null): string[] {
  if (!s) return [];
  return s
    .split(/[,，、]\s*/)
    .map((n) => n.trim())
    .filter((n) => n.length > 0);
}
