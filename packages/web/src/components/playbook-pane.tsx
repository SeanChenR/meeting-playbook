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
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MarkdownPreview } from "../lib/markdown-preview";
import {
  PlaybookApiError,
  playbookQueryOptions,
  useUpsertPlaybookMutation,
} from "../lib/playbook-api";
import { Pane } from "./pane";
import { Alert } from "./ui/alert";
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

  const [freeformMode, setFreeformMode] = useState<"edit" | "preview">("edit");
  const [draft, setDraft] = useState<string>("");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setDraft(query.data.free_form_markdown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.id]);

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
  const error = fetchError ?? saveError;

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
    </Pane>
  );
}
