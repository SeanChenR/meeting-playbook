/**
 * TagPicker — slice-17 task 5.3.
 *
 * Popover with a search input + existing-tag list + inline-create row that
 * appears when the search text matches no existing tag. Designed to be
 * mounted in the meeting detail header so the user can attach / detach tags
 * to that meeting.
 *
 * Behavior:
 * - The trigger button shows a `+ 新增標籤 / + Add tag` label.
 * - When opened: GET /api/tags is fetched (or read from the react-query
 *   cache). Existing tags are listed; clicking one toggles its attached
 *   state (attach if not present, detach if already in `currentTags`).
 * - Typing in the search input filters the list; when the query is not a
 *   trim()-case-insensitive match against any existing tag, an inline-create
 *   row appears. Clicking it issues `POST /api/tags` then chains
 *   `POST /api/meetings/{id}/tags` with the returned id.
 *
 * Popover backend: Radix `react-popover` rendered in a Portal so the panel
 * escapes any `overflow-hidden` ancestor (e.g. the meetings-kanban column
 * that previously clipped the popover and pushed a horizontal scrollbar).
 */

import * as Popover from "@radix-ui/react-popover";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type Tag,
  useAttachTagMutation,
  useCreateTagMutation,
  useDetachTagMutation,
  useTagsListQuery,
} from "../../lib/tags-api";
import { TAG_PALETTE } from "../../lib/tag-palette";
import { cn } from "../../lib/utils";
import { TagChip } from "./tag-chip";

/** A slim tag shape — full `Tag` objects from the API are accepted too. */
export interface TagPickerCurrentTag {
  id: string;
  name: string;
  color: string;
}

export interface TagPickerProps {
  meetingId: string;
  currentTags: TagPickerCurrentTag[];
  onAttached?: (tag: Tag) => void;
  onDetached?: (tagId: string) => void;
}

export function TagPicker({ meetingId, currentTags, onAttached, onDetached }: TagPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const tagsQuery = useTagsListQuery();
  const createMutation = useCreateTagMutation();
  const attachMutation = useAttachTagMutation(meetingId);
  const detachMutation = useDetachTagMutation(meetingId);

  const attachedIds = useMemo(() => new Set(currentTags.map((t) => t.id)), [currentTags]);

  const trimmedQuery = query.trim();
  // Defensive: some test fetch handlers return `{}` (object, not array)
  // for unmatched URLs. Guard so an unexpected non-array response can't
  // crash the picker on first render.
  const all = useMemo<Tag[]>(
    () => (Array.isArray(tagsQuery.data) ? tagsQuery.data : []),
    [tagsQuery.data],
  );

  const filtered = useMemo(() => {
    if (!trimmedQuery) return all;
    const needle = trimmedQuery.toLowerCase();
    return all.filter((tag) => tag.name.toLowerCase().includes(needle));
  }, [all, trimmedQuery]);

  const exactMatch = useMemo(
    () =>
      trimmedQuery.length > 0 &&
      all.some((tag) => tag.name.toLowerCase() === trimmedQuery.toLowerCase()),
    [all, trimmedQuery],
  );
  const showCreateRow = trimmedQuery.length > 0 && !exactMatch;

  // Radix Popover owns the close-on-outside-click + Escape handling. We
  // still focus the search input on open so the keyboard flow lands in
  // the right place immediately.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function _toggleAttach(tag: Tag) {
    if (attachedIds.has(tag.id)) {
      await detachMutation.mutateAsync(tag.id);
      onDetached?.(tag.id);
    } else {
      await attachMutation.mutateAsync(tag.id);
      onAttached?.(tag);
    }
  }

  async function _createAndAttach() {
    if (!trimmedQuery) return;
    const created = await createMutation.mutateAsync({
      name: trimmedQuery,
      color: TAG_PALETTE[0],
    });
    await attachMutation.mutateAsync(created.id);
    onAttached?.(created);
    setQuery("");
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          data-testid="tag-picker-trigger"
          className={cn(
            "inline-flex items-center gap-1 rounded-full border border-dashed border-(--color-border)",
            "px-2.5 py-1 text-xs font-medium text-(--color-muted-foreground)",
            "transition-colors hover:border-(--color-primary)/40 hover:text-(--color-foreground)",
          )}
        >
          {t("tags.picker.trigger")}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          data-testid="tag-picker-panel"
          align="end"
          sideOffset={6}
          collisionPadding={12}
          // `data-side` flips automatically — top/bottom + left/right by
          // available viewport room. Portal output sits on `document.body`
          // so kanban-column `overflow-hidden` no longer clips this panel.
          className={cn(
            "z-50 w-64 rounded-md border border-(--color-border)",
            "bg-(--color-card) p-2 shadow-lg",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1",
          )}
        >
          <input
            ref={inputRef}
            data-testid="tag-picker-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("tags.picker.placeholder")}
            className="mb-2 w-full rounded-sm border border-(--color-border) bg-(--color-card) px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-(--color-primary)/40"
          />
          <ul className="max-h-60 overflow-y-auto" role="listbox">
            {filtered.length === 0 && !showCreateRow && (
              <li className="px-2 py-1 text-xs text-(--color-muted-foreground)">
                {t("tags.picker.noResults")}
              </li>
            )}
            {filtered.map((tag) => {
              const isAttached = attachedIds.has(tag.id);
              return (
                <li
                  key={tag.id}
                  data-testid={`tag-picker-row-${tag.id}`}
                  data-attached={isAttached}
                  role="option"
                  aria-selected={isAttached}
                  className="flex cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-1 hover:bg-(--color-muted)"
                  onClick={() => {
                    void _toggleAttach(tag);
                  }}
                >
                  <TagChip name={tag.name} color={tag.color} />
                  {isAttached && (
                    <span className="text-xs text-(--color-primary)" aria-hidden>
                      ✓
                    </span>
                  )}
                </li>
              );
            })}
            {showCreateRow && (
              <li
                data-testid="tag-picker-create-row"
                role="option"
                className="cursor-pointer rounded-sm px-2 py-1 text-sm text-(--color-foreground) hover:bg-(--color-muted)"
                onClick={() => {
                  void _createAndAttach();
                }}
              >
                {t("tags.picker.create", { query: trimmedQuery })}
              </li>
            )}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
