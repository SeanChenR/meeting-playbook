/**
 * PlaybookPane — slice ui-overhaul-claude-design task 6.4.
 *
 * Re-skinned to use the shared `Pane` shell with the design-bundle's
 * accent bar + "AI 草稿" badge + actions slot. Freeform Markdown editor
 * (textarea + read-only preview) is preserved verbatim — structured 6-field
 * view stays deferred per project memory `playbook_field_set_open`.
 *
 * The Edit / Preview sub-toggle keeps its prior data-testids
 * (`freeform-edit-tab` / `freeform-preview-tab`) so the existing tests
 * still resolve. Save behavior + i18n keys + PlaybookApiError handling
 * are unchanged from slice-7 round 3.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MarkdownPreview } from "../lib/markdown-preview";
import {
  PlaybookApiError,
  playbookQueryOptions,
  useRegeneratePlaybookMutation,
  useUpsertPlaybookMutation,
} from "../lib/playbook-api";
import { Pane } from "./pane";
import { Alert } from "./ui/alert";
import { AlertDialog } from "./ui/alert-dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { cn } from "../lib/utils";

interface PlaybookPaneProps {
  meetingId: string;
}

const TEXTAREA_CLASSNAME = cn(
  "flex w-full min-h-[160px] rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
  "placeholder:text-(--color-muted-foreground)",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

export function PlaybookPane({ meetingId }: PlaybookPaneProps) {
  const { t } = useTranslation();
  const query = useQuery(playbookQueryOptions(meetingId));
  const mutation = useUpsertPlaybookMutation(meetingId);
  const regenerateMutation = useRegeneratePlaybookMutation(meetingId);

  const [freeformMode, setFreeformMode] = useState<"edit" | "preview">("edit");
  const [draft, setDraft] = useState<string>("");
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [showRegenerateDialog, setShowRegenerateDialog] = useState(false);

  useEffect(() => {
    if (!query.data) return;
    setDraft(query.data.free_form_markdown);
    setSavedAt(null);
    // Re-sync on `updated_at` so regenerate (which keeps the playbook
    // row id but writes a new `updated_at`) replaces the textarea with
    // the freshly generated markdown. Watching only `id` left the
    // draft stuck on the pre-regenerate content even though the query
    // cache had already updated, making the regenerate button look
    // like a no-op.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.id, query.data?.updated_at]);

  async function handleSave() {
    try {
      await mutation.mutateAsync({
        free_form_markdown: draft,
        objective: query.data?.objective ?? "",
        counterparty_profile: query.data?.counterparty_profile ?? "",
        anticipated_topics: query.data?.anticipated_topics ?? "",
        anticipated_objections: query.data?.anticipated_objections ?? "",
        talking_points: query.data?.talking_points ?? "",
        red_lines: query.data?.red_lines ?? "",
      });
      setSavedAt(Date.now());
      toast.success(t("playbook.save.saved_toast"));
    } catch {
      // mutation.error surfaced below; nothing else to do here.
    }
  }

  const fetchError = query.isError
    ? query.error instanceof PlaybookApiError && query.error.errorCode
      ? localizedErrorMessage(query.error.errorCode, t)
      : t("playbook.errors.fallback")
    : null;
  const saveError = mutation.isError
    ? mutation.error instanceof PlaybookApiError && mutation.error.errorCode
      ? localizedErrorMessage(mutation.error.errorCode, t)
      : t("playbook.errors.fallback")
    : null;
  const regenerateError = regenerateMutation.isError
    ? regenerateMutation.error instanceof PlaybookApiError && regenerateMutation.error.errorCode
      ? localizedErrorMessage(regenerateMutation.error.errorCode, t)
      : t("playbook.stale.regenerate_failed")
    : null;
  const error = fetchError ?? saveError ?? regenerateError;

  const saveLabel = mutation.isPending
    ? t("playbook.save.saving")
    : savedAt
      ? t("playbook.save.saved")
      : t("playbook.save.idle");

  return (
    <Pane
      data-testid="playbook-pane"
      title={t("playbook.heading")}
      accent="var(--color-primary)"
      badge={
        <Badge variant="outline" data-testid="playbook-ai-draft-badge">
          {t("playbook.aiDraftBadge")}
        </Badge>
      }
      actions={
        <div role="group" aria-label="freeform sub-mode" className="inline-flex gap-1">
          <Button
            type="button"
            size="sm"
            variant={freeformMode === "edit" ? "primary" : "ghost"}
            aria-pressed={freeformMode === "edit"}
            data-testid="freeform-edit-tab"
            onClick={() => setFreeformMode("edit")}
          >
            {t("playbook.freeform.editTab")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={freeformMode === "preview" ? "primary" : "ghost"}
            aria-pressed={freeformMode === "preview"}
            data-testid="freeform-preview-tab"
            onClick={() => setFreeformMode("preview")}
          >
            {t("playbook.freeform.previewTab")}
          </Button>
        </div>
      }
      bodyClassName="px-3.5 py-3.5"
    >
      <div className="space-y-4">
        {query.isLoading && (
          <p className="text-sm text-(--color-muted-foreground)">{t("playbook.loading")}</p>
        )}
        {error && <Alert variant="destructive">{error}</Alert>}

        {query.data?.is_stale && (
          <Alert
            data-testid="playbook-stale-attachments-banner"
            variant="warning"
            role="note"
            className="flex flex-wrap items-center gap-3"
          >
            <span className="flex-1">{t("playbook.stale.attachments_changed")}</span>
            <Button
              type="button"
              size="sm"
              data-testid="playbook-stale-regenerate-button"
              disabled={regenerateMutation.isPending}
              onClick={() => {
                // Only confirm when there's content to lose; first-ever
                // generation (empty draft) goes straight through.
                if (draft.trim().length > 0) {
                  setShowRegenerateDialog(true);
                } else {
                  regenerateMutation.mutate();
                }
              }}
            >
              {regenerateMutation.isPending
                ? t("playbook.stale.regenerating")
                : t("playbook.stale.regenerate_button")}
            </Button>
          </Alert>
        )}

        <div className="space-y-2">
          <Label htmlFor="playbook-freeform">{t("playbook.freeform.label")}</Label>
          {freeformMode === "edit" ? (
            <textarea
              id="playbook-freeform"
              className={TEXTAREA_CLASSNAME}
              placeholder={t("playbook.freeform.placeholder")}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setSavedAt(null);
              }}
              rows={12}
            />
          ) : (
            <MarkdownPreview source={draft} />
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button type="button" onClick={handleSave} disabled={mutation.isPending} size="sm">
            {saveLabel}
          </Button>
        </div>
      </div>

      <AlertDialog
        open={showRegenerateDialog}
        onOpenChange={setShowRegenerateDialog}
        title={t("playbook.stale.confirm_title")}
        description={t("playbook.stale.confirm_description")}
        confirmLabel={t("playbook.stale.confirm_confirm")}
        cancelLabel={t("playbook.stale.confirm_cancel")}
        destructive
        onConfirm={() => regenerateMutation.mutate()}
      />
    </Pane>
  );
}
