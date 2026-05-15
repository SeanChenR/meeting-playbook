/**
 * TagFilter — slice-17 task 5.3.
 *
 * Multi-select dropdown that reads + writes `?tag_ids=` URL search params
 * (per design decision "用 search param 不用 path"). State lives in the URL
 * so a page reload preserves the filter and all three meeting views (list /
 * kanban / calendar) share the same selection.
 *
 * Trigger label: "標籤 (N)" / "Tags (N)" — N is the selected count.
 *
 * The dropdown is hand-rolled (no Radix popover); a click outside + Escape
 * closes the panel. The component intentionally uses `useLocation` +
 * `useNavigate` from TanStack Router rather than the global URL so it works
 * inside the synthetic test memory history fixture.
 */

import { useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useTagsListQuery } from "../../lib/tags-api";
import { cn } from "../../lib/utils";
import { TagChip } from "./tag-chip";

function _parseTagIds(search: string): string[] {
  // search may already be parsed by TanStack Router into an object, but the
  // raw form (e.g. "?tag_ids=a,b") is the canonical wire format because the
  // backend reads the same comma-separated list. Splitting via URLSearchParams
  // keeps the parse robust against re-ordering / extra query params.
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const raw = params.get("tag_ids");
  if (!raw) return [];
  return raw.split(",").filter(Boolean);
}

function _writeTagIds(search: string, tagIds: string[]): string {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if (tagIds.length === 0) params.delete("tag_ids");
  else params.set("tag_ids", tagIds.join(","));
  const q = params.toString();
  return q.length > 0 ? `?${q}` : "";
}

export function TagFilter() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const tagsQuery = useTagsListQuery();
  const tags = tagsQuery.data ?? [];

  const selected = useMemo(() => _parseTagIds(location.searchStr ?? ""), [location.searchStr]);
  const selectedCount = selected.length;

  useEffect(() => {
    if (!open) return;
    function _onDocClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function _onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", _onDocClick);
    document.addEventListener("keydown", _onKey);
    return () => {
      document.removeEventListener("mousedown", _onDocClick);
      document.removeEventListener("keydown", _onKey);
    };
  }, [open]);

  function _toggle(tagId: string) {
    const next = selected.includes(tagId)
      ? selected.filter((id) => id !== tagId)
      : [...selected, tagId];
    const nextSearch = _writeTagIds(location.searchStr ?? "", next);
    navigate({
      to: location.pathname,
      search: () => {
        const params = new URLSearchParams(
          nextSearch.startsWith("?") ? nextSearch.slice(1) : nextSearch,
        );
        const obj: Record<string, string> = {};
        params.forEach((v, k) => {
          obj[k] = v;
        });
        return obj;
      },
    } as never);
  }

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        data-testid="tag-filter-trigger"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center gap-2 rounded-md border border-(--color-border)",
          "px-3 py-1.5 text-sm font-medium text-(--color-foreground)",
          "transition-colors hover:border-(--color-primary)/40 hover:bg-(--color-muted)/40",
        )}
      >
        <span>{t("tags.filter.label")}</span>
        {/* Count is rendered as its own node so the value is observable even
            when the i18n key has not yet been populated (test fixtures). */}
        <span data-testid="tag-filter-trigger-count">({selectedCount})</span>
      </button>
      {open && (
        <div
          data-testid="tag-filter-panel"
          className={cn(
            "absolute right-0 z-50 mt-1 w-64 rounded-md border border-(--color-border)",
            "bg-(--color-card) p-2 shadow-md",
          )}
        >
          {tags.length === 0 ? (
            <p className="px-2 py-1 text-xs text-(--color-muted-foreground)">
              {t("tags.filter.empty")}
            </p>
          ) : (
            <ul className="max-h-60 overflow-y-auto" role="listbox">
              {tags.map((tag) => {
                const isSelected = selected.includes(tag.id);
                return (
                  <li
                    key={tag.id}
                    data-testid={`tag-filter-option-${tag.id}`}
                    data-selected={isSelected}
                    role="option"
                    aria-selected={isSelected}
                    className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 hover:bg-(--color-muted)"
                    onClick={() => _toggle(tag.id)}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      readOnly
                      tabIndex={-1}
                      className="size-3.5"
                    />
                    <TagChip name={tag.name} color={tag.color} />
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
