/**
 * /settings/tags — slice-17 task 6.2.
 *
 * Tag CRUD management page. Renders one row per tag with:
 * - Tag chip preview
 * - Inline rename (text input + submit / cancel)
 * - Recolor swatch picker (preset palette only — no free-form hex input)
 * - Hard delete with confirmation AlertDialog whose description carries
 *   the current `meeting_count` (via ICU plural in en; single form in zh-TW).
 *
 * The list source is `GET /api/tags?with_meeting_count=true` so the delete
 * confirmation can describe the impact without an extra round-trip.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ProtectedShell } from "../../components/protected-shell";
import { TagChip } from "../../components/tags/tag-chip";
import { AlertDialog } from "../../components/ui/alert-dialog";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { TAG_PALETTE } from "../../lib/tag-palette";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  ApiError,
  type Tag,
  useCreateTagMutation,
  useDeleteTagMutation,
  useTagsListQuery,
  useUpdateTagMutation,
} from "../../lib/tags-api";

interface RenameState {
  tagId: string;
  value: string;
  error: string | null;
}

interface RecolorOpen {
  tagId: string | null;
}

interface DeleteDialogState {
  tag: Tag | null;
}

export function SettingsTags() {
  const { t } = useTranslation();
  const tagsQuery = useTagsListQuery({ withMeetingCount: true });
  const createMutation = useCreateTagMutation();
  const updateMutation = useUpdateTagMutation();
  const deleteMutation = useDeleteTagMutation();

  const [rename, setRename] = useState<RenameState | null>(null);
  const [recolorOpen, setRecolorOpen] = useState<RecolorOpen>({ tagId: null });
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({ tag: null });

  // Slice-17 polish: inline "+ 新增標籤" form. Hidden until the user
  // clicks the CTA; collapses again on submit / cancel.
  const [createForm, setCreateForm] = useState<{
    name: string;
    color: string;
    error: string | null;
  } | null>(null);

  async function _submitCreate() {
    if (!createForm) return;
    const trimmed = createForm.name.trim();
    if (trimmed.length === 0) {
      setCreateForm({ ...createForm, error: t("settings.tags.create.emptyName") });
      return;
    }
    try {
      await createMutation.mutateAsync({ name: trimmed, color: createForm.color });
      setCreateForm(null);
    } catch (err) {
      const code = err instanceof ApiError ? err.errorCode : undefined;
      const message = code ? localizedErrorMessage(code, t) : t("errors.common.unknown");
      setCreateForm({ ...createForm, error: message });
    }
  }

  const tags = tagsQuery.data ?? [];

  async function _submitRename() {
    if (!rename) return;
    try {
      await updateMutation.mutateAsync({
        tagId: rename.tagId,
        payload: { name: rename.value },
      });
      setRename(null);
    } catch (err) {
      const code = err instanceof ApiError ? err.errorCode : undefined;
      const message = code ? localizedErrorMessage(code, t) : t("errors.common.unknown");
      setRename({ ...rename, error: message });
    }
  }

  async function _submitRecolor(tagId: string, color: string) {
    try {
      await updateMutation.mutateAsync({ tagId, payload: { color } });
      setRecolorOpen({ tagId: null });
    } catch {
      // Palette-only picker — server-side rejection here is unexpected;
      // close the popover defensively. The list will re-fetch and surface
      // the rejected change via the cache invalidation.
      setRecolorOpen({ tagId: null });
    }
  }

  async function _confirmDelete() {
    if (!deleteDialog.tag) return;
    try {
      await deleteMutation.mutateAsync(deleteDialog.tag.id);
    } finally {
      setDeleteDialog({ tag: null });
    }
  }

  return (
    <ProtectedShell>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-(--color-foreground)">
            {t("settings.tags.title")}
          </h1>
          <p className="text-sm text-(--color-muted-foreground)">{t("settings.tags.subtitle")}</p>
        </div>
        {createForm === null && (
          <Button
            type="button"
            data-testid="settings-tags-create-cta"
            onClick={() =>
              setCreateForm({
                name: "",
                color: TAG_PALETTE[0] ?? "",
                error: null,
              })
            }
          >
            {t("settings.tags.create.cta")}
          </Button>
        )}
      </header>

      {createForm !== null && (
        <Card data-testid="settings-tags-create-form">
          <CardContent className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Input
                data-testid="settings-tags-create-name"
                autoFocus
                value={createForm.name}
                placeholder={t("settings.tags.create.namePlaceholder")}
                maxLength={30}
                onChange={(e) =>
                  setCreateForm({ ...createForm, name: e.target.value, error: null })
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void _submitCreate();
                  } else if (e.key === "Escape") {
                    setCreateForm(null);
                  }
                }}
                className="flex-1 min-w-[200px]"
              />
              <div className="flex gap-1.5">
                {TAG_PALETTE.map((color) => (
                  <button
                    key={color}
                    type="button"
                    data-testid={`settings-tags-create-color-${color}`}
                    onClick={() => setCreateForm({ ...createForm, color, error: null })}
                    aria-label={color}
                    style={{ background: color }}
                    className={
                      createForm.color === color
                        ? "size-6 rounded-full border-2 border-(--color-foreground) transition-transform"
                        : "size-6 rounded-full border border-(--color-border) transition-transform hover:scale-110"
                    }
                  />
                ))}
              </div>
              <Button
                type="button"
                data-testid="settings-tags-create-submit"
                disabled={createForm.name.trim().length === 0}
                onClick={() => void _submitCreate()}
              >
                {t("settings.tags.create.submit")}
              </Button>
              <Button
                type="button"
                variant="outline"
                data-testid="settings-tags-create-cancel"
                onClick={() => setCreateForm(null)}
              >
                {t("settings.tags.create.cancel")}
              </Button>
            </div>
            {createForm.error && (
              <p
                data-testid="settings-tags-create-error"
                className="text-xs text-(--color-destructive)"
              >
                {createForm.error}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="divide-y divide-(--color-border) p-0">
          {tags.length === 0 && (
            <p
              data-testid="settings-tags-empty"
              className="px-4 py-8 text-center text-sm text-(--color-muted-foreground)"
            >
              {t("settings.tags.empty")}
            </p>
          )}
          {tags.map((tag) => {
            const isRenaming = rename?.tagId === tag.id;
            const isRecoloring = recolorOpen.tagId === tag.id;
            return (
              <div
                key={tag.id}
                data-testid={`settings-tags-row-${tag.id}`}
                className="flex flex-wrap items-center gap-3 px-4 py-3"
              >
                {isRenaming ? (
                  <div className="flex items-center gap-2">
                    <Input
                      data-testid="settings-tags-rename-input"
                      autoFocus
                      value={rename.value}
                      onChange={(e) => setRename({ ...rename, value: e.target.value, error: null })}
                      className="h-8 w-48"
                    />
                    <Button
                      type="button"
                      size="sm"
                      data-testid="settings-tags-rename-submit"
                      onClick={() => void _submitRename()}
                    >
                      {t("settings.tags.renameSubmit")}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setRename(null)}
                    >
                      {t("settings.tags.renameCancel")}
                    </Button>
                    {rename.error && (
                      <span
                        data-testid="settings-tags-rename-error"
                        className="text-xs text-(--color-destructive)"
                      >
                        {rename.error}
                      </span>
                    )}
                  </div>
                ) : (
                  <TagChip name={tag.name} color={tag.color} size="md" />
                )}

                <span
                  data-testid={`settings-tags-meeting-count-${tag.id}`}
                  className="text-xs text-(--color-muted-foreground)"
                >
                  {t("settings.tags.meetingCount", { count: tag.meeting_count ?? 0 })}
                </span>

                <div className="ml-auto flex items-center gap-2">
                  {!isRenaming && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      data-testid="settings-tags-rename-button"
                      onClick={() => setRename({ tagId: tag.id, value: tag.name, error: null })}
                    >
                      {t("settings.tags.renameAction")}
                    </Button>
                  )}
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    data-testid="settings-tags-recolor-button"
                    onClick={() =>
                      setRecolorOpen({
                        tagId: isRecoloring ? null : tag.id,
                      })
                    }
                  >
                    {t("settings.tags.recolorAction")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    data-testid="settings-tags-delete-button"
                    onClick={() => setDeleteDialog({ tag: tag as Tag })}
                  >
                    {t("settings.tags.deleteAction")}
                  </Button>
                </div>

                {isRecoloring && (
                  <div
                    data-testid="settings-tags-recolor-swatches"
                    className="mt-2 flex w-full flex-wrap gap-2"
                  >
                    {TAG_PALETTE.map((color) => (
                      <button
                        key={color}
                        type="button"
                        aria-label={color}
                        onClick={() => void _submitRecolor(tag.id, color)}
                        className="size-6 rounded-full border border-(--color-border)"
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      <AlertDialog
        open={deleteDialog.tag !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteDialog({ tag: null });
        }}
        title={t("settings.tags.deleteConfirm.title", {
          name: deleteDialog.tag?.name ?? "",
        })}
        description={
          <span data-testid="settings-tags-delete-description">
            {t("settings.tags.deleteConfirm.description", {
              count: deleteDialog.tag?.meeting_count ?? 0,
            })}
          </span>
        }
        cancelLabel={t("settings.tags.deleteConfirm.cancel")}
        confirmLabel={t("settings.tags.deleteConfirm.confirm")}
        onConfirm={() => {
          void _confirmDelete();
        }}
        destructive
      />
      {/* Hidden testid for confirm button so tests can target it directly */}
      <div className="sr-only">
        {deleteDialog.tag !== null && (
          <button
            type="button"
            data-testid="settings-tags-delete-confirm"
            onClick={() => {
              void _confirmDelete();
            }}
          >
            confirm
          </button>
        )}
      </div>
    </ProtectedShell>
  );
}
