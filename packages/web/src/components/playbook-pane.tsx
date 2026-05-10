import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import {
  PlaybookApiError,
  playbookQueryOptions,
  useUpsertPlaybookMutation,
} from "../lib/playbook-api";
import { MarkdownPreview } from "../lib/markdown-preview";
import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
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

  // Slice-7 round 3: structured tab removed per Sean's call — only freeform
  // markdown remains. Sub-toggle still switches Edit / Preview within freeform.
  const [freeformMode, setFreeformMode] = useState<"edit" | "preview">("edit");
  const [draft, setDraft] = useState<string>("");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Initialize draft from server once.
  useEffect(() => {
    if (!query.data) return;
    setDraft(query.data.free_form_markdown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.id]);

  async function handleSave() {
    try {
      // Backend playbook PUT still accepts the full 7-field shape. Send the
      // textarea value as `free_form_markdown` and pass empty strings for the
      // other fields so the schema stays satisfied without dropping data the
      // user might have set via the LLM-generated draft.
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
    <Card className="flex h-full flex-col">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>{t("playbook.heading")}</CardTitle>
        {/* Slice-7 round 3: Edit / Preview sub-toggle promoted to header. */}
        <div role="group" aria-label="freeform sub-mode" className="flex gap-1">
          <Button
            type="button"
            size="sm"
            variant={freeformMode === "edit" ? "primary" : "outline"}
            aria-pressed={freeformMode === "edit"}
            data-testid="freeform-edit-tab"
            onClick={() => setFreeformMode("edit")}
          >
            {t("playbook.freeform.editTab")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={freeformMode === "preview" ? "primary" : "outline"}
            aria-pressed={freeformMode === "preview"}
            data-testid="freeform-preview-tab"
            onClick={() => setFreeformMode("preview")}
          >
            {t("playbook.freeform.previewTab")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col space-y-4 overflow-y-auto">
        {query.isLoading && <div>{t("playbook.loading")}</div>}
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
          <Button type="button" onClick={handleSave} disabled={mutation.isPending}>
            {saveLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
