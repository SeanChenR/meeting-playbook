import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import {
  PlaybookApiError,
  playbookQueryOptions,
  useUpsertPlaybookMutation,
} from "../lib/playbook-api";
import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Label } from "./ui/label";
import { cn } from "../lib/utils";

interface PlaybookPaneProps {
  meetingId: string;
}

type ViewMode = "freeform" | "structured";

const STRUCTURED_FIELDS = [
  { key: "objective", labelKey: "playbook.fields.objective" },
  { key: "counterparty_profile", labelKey: "playbook.fields.counterpartyProfile" },
  { key: "anticipated_topics", labelKey: "playbook.fields.anticipatedTopics" },
  { key: "anticipated_objections", labelKey: "playbook.fields.anticipatedObjections" },
  { key: "talking_points", labelKey: "playbook.fields.talkingPoints" },
  { key: "red_lines", labelKey: "playbook.fields.redLines" },
] as const;

type ContentField =
  | "free_form_markdown"
  | "objective"
  | "counterparty_profile"
  | "anticipated_topics"
  | "anticipated_objections"
  | "talking_points"
  | "red_lines";

const EMPTY_DRAFT: Record<ContentField, string> = {
  free_form_markdown: "",
  objective: "",
  counterparty_profile: "",
  anticipated_topics: "",
  anticipated_objections: "",
  talking_points: "",
  red_lines: "",
};

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

  const [view, setView] = useState<ViewMode>("freeform");
  const [draft, setDraft] = useState<Record<ContentField, string>>(EMPTY_DRAFT);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Initialize draft once when the query settles. Subsequent server changes
  // do not silently overwrite the user's local edits.
  useEffect(() => {
    if (!query.data) return;
    setDraft({
      free_form_markdown: query.data.free_form_markdown,
      objective: query.data.objective,
      counterparty_profile: query.data.counterparty_profile,
      anticipated_topics: query.data.anticipated_topics,
      anticipated_objections: query.data.anticipated_objections,
      talking_points: query.data.talking_points,
      red_lines: query.data.red_lines,
    });
    // Only re-sync on first successful load (data identity); deliberate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.id]);

  const updateField = (field: ContentField) => (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDraft((prev) => ({ ...prev, [field]: e.target.value }));
    setSavedAt(null);
  };

  async function handleSave() {
    try {
      await mutation.mutateAsync(draft);
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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>{t("playbook.heading")}</CardTitle>
        <div role="group" aria-label="playbook view" className="flex gap-1">
          <Button
            type="button"
            size="sm"
            variant={view === "freeform" ? "primary" : "outline"}
            aria-pressed={view === "freeform"}
            onClick={() => setView("freeform")}
          >
            {t("playbook.toggle.freeform")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={view === "structured" ? "primary" : "outline"}
            aria-pressed={view === "structured"}
            onClick={() => setView("structured")}
          >
            {t("playbook.toggle.structured")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {query.isLoading && <div>{t("playbook.loading")}</div>}
        {error && <Alert variant="destructive">{error}</Alert>}

        {view === "freeform" && (
          <div className="space-y-1">
            <Label htmlFor="playbook-freeform">{t("playbook.freeform.label")}</Label>
            <textarea
              id="playbook-freeform"
              className={TEXTAREA_CLASSNAME}
              placeholder={t("playbook.freeform.placeholder")}
              value={draft.free_form_markdown}
              onChange={updateField("free_form_markdown")}
              rows={12}
            />
          </div>
        )}

        {view === "structured" && (
          <div className="space-y-4">
            {STRUCTURED_FIELDS.map(({ key, labelKey }) => (
              <div key={key} className="space-y-1">
                <Label htmlFor={`playbook-${key}`}>{t(labelKey)}</Label>
                <textarea
                  id={`playbook-${key}`}
                  className={TEXTAREA_CLASSNAME}
                  value={draft[key]}
                  onChange={updateField(key)}
                  rows={4}
                />
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="button" onClick={handleSave} disabled={mutation.isPending}>
            {saveLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
