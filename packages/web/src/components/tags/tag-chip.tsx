/**
 * TagChip — slice-17 task 5.2.
 *
 * Display-only chip. Picks a readable text-color variant from the supplied
 * background using `pickReadableTextColor` (light text on dark bg, dark on
 * light). Mounted by meeting card / kanban card / calendar pill / detail
 * header / inside `<TagFilter>` selected items.
 *
 * Sizes:
 *   - `sm` (default) → padding 0.5/2, text-xs
 *   - `md`          → padding 1/2.5, text-sm
 */

import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";
import { pickReadableTextColor } from "../../lib/tag-palette";

export interface TagChipProps {
  name: string;
  color: string;
  onRemove?: () => void;
  size?: "sm" | "md";
}

export function TagChip({ name, color, onRemove, size = "sm" }: TagChipProps) {
  const { t } = useTranslation();
  const variant = pickReadableTextColor(color);
  const isDark = variant === "dark";

  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";

  return (
    <span
      data-testid="tag-chip"
      data-text-variant={variant}
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-full font-medium leading-none",
        sizeClasses,
        // Tag colors are theme-invariant (fixed palette) — the readable text
        // colour must NOT swap with the app theme. `text-[#1a1a1a]` matches
        // the DARK_FG_HEX threshold used in `pickReadableTextColor` for
        // contrast computation; `text-white` matches LIGHT_FG_HEX.
        isDark ? "text-[#1a1a1a]" : "text-white",
      )}
      style={{ backgroundColor: color }}
    >
      <span className="truncate">{name}</span>
      {onRemove !== undefined && (
        <button
          type="button"
          data-testid="tag-chip-remove"
          aria-label={t("tags.chip.removeAria", { name })}
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            onRemove();
          }}
          className={cn(
            "inline-flex size-3.5 items-center justify-center rounded-full transition-opacity hover:opacity-70",
            isDark ? "text-[#1a1a1a]/70" : "text-white/80",
          )}
        >
          <X className="size-3" aria-hidden />
        </button>
      )}
    </span>
  );
}
