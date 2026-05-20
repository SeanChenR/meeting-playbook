/**
 * PlaybookPane — slice ui-overhaul-claude-design + claude-design v2 alignment.
 *
 * Header dropped its duplicated column title (now the only title row, via
 * <Pane>). The "AI 草稿" badge became a violet sparkle chip; Save lives in
 * the Pane's actions slot next to the Edit/Preview toggle (no detached
 * primary block). Successful saves surface a <SuccessResultOverlay>
 * hazeover instead of a toast.
 */

import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MarkdownPreview } from "../lib/markdown-preview";
import {
  PlaybookApiError,
  playbookQueryOptions,
  useDiscardPreviousPlaybookMutation,
  useRegeneratePlaybookMutation,
  useRestorePreviousPlaybookMutation,
  useUpsertPlaybookMutation,
} from "../lib/playbook-api";
import { cn } from "../lib/utils";
import { Pane } from "./pane";
import { PlaybookDiffViewer, type HunkDecisions } from "./playbook-diff-viewer";
import { SuccessResultOverlay } from "./success-result-overlay";
import { Alert } from "./ui/alert";
import { AlertDialog } from "./ui/alert-dialog";
import { Button } from "./ui/button";
import { SpicyReveal } from "./ui/spicy-reveal";

interface PlaybookPaneProps {
  meetingId: string;
}

const TEXTAREA_CLASSNAME = cn(
  "flex w-full min-h-[160px] rounded-md border border-(--color-input) bg-(--color-card) px-3 py-2 text-sm",
  "placeholder:text-(--color-muted-foreground)",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

function AiDraftChip({ label }: { label: string }) {
  return (
    <span
      data-testid="playbook-ai-draft-badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        "bg-(--color-primary)/12 text-(--color-primary)",
        "ring-1 ring-(--color-primary)/25 ring-inset",
      )}
    >
      <Sparkles className="size-3" strokeWidth={2} aria-hidden />
      {label}
    </span>
  );
}

function SubModeToggle({
  value,
  onChange,
  showDiff,
  labels,
}: {
  value: "edit" | "preview" | "diff";
  onChange: (next: "edit" | "preview" | "diff") => void;
  showDiff: boolean;
  labels: { edit: string; preview: string; diff: string };
}) {
  const options: Array<{ key: "edit" | "preview" | "diff"; testId: string; label: string }> = [
    { key: "edit", testId: "freeform-edit-tab", label: labels.edit },
    { key: "preview", testId: "freeform-preview-tab", label: labels.preview },
  ];
  if (showDiff) {
    options.push({ key: "diff", testId: "freeform-diff-tab", label: labels.diff });
  }
  return (
    <div
      role="group"
      aria-label="freeform sub-mode"
      className={cn(
        "inline-flex items-center rounded-(--radius-md) p-0.5",
        // Aura-tinted track — replaces the grey surface-2 + border ring.
        "bg-(--color-primary)/8 ring-1 ring-(--color-primary)/15",
      )}
    >
      {options.map((opt) => {
        const active = value === opt.key;
        return (
          <button
            key={opt.key}
            type="button"
            data-testid={opt.testId}
            aria-pressed={active}
            onClick={() => onChange(opt.key)}
            className={cn(
              "rounded-[calc(var(--radius-md)-2px)] px-2.5 py-1 text-[12px] font-medium transition-colors",
              active
                ? "bg-(--color-primary) text-(--color-primary-foreground) shadow-(--shadow-sm)"
                : "text-(--color-primary)/70 hover:text-(--color-primary)",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function PlaybookPane({ meetingId }: PlaybookPaneProps) {
  const { t } = useTranslation();
  const query = useQuery(playbookQueryOptions(meetingId));
  const mutation = useUpsertPlaybookMutation(meetingId);
  const regenerateMutation = useRegeneratePlaybookMutation(meetingId);
  const discardPreviousMutation = useDiscardPreviousPlaybookMutation(meetingId);
  const restorePreviousMutation = useRestorePreviousPlaybookMutation(meetingId);

  const [freeformMode, setFreeformMode] = useState<"edit" | "preview" | "diff">("preview");
  const [draft, setDraft] = useState<string>("");
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [showRegenerateDialog, setShowRegenerateDialog] = useState(false);
  const [diffDecisions, setDiffDecisions] = useState<HunkDecisions>({});
  const [successOpen, setSuccessOpen] = useState(false);

  useEffect(() => {
    if (!query.data) return;
    setDraft(query.data.free_form_markdown);
    setSavedAt(null);
    setDiffDecisions({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.id, query.data?.updated_at]);

  useEffect(() => {
    const data = regenerateMutation.data;
    if (!data) return;
    if (
      data.previous_free_form_markdown &&
      data.previous_free_form_markdown !== data.free_form_markdown
    ) {
      setFreeformMode("diff");
    }
  }, [regenerateMutation.data]);

  useEffect(() => {
    if (freeformMode === "diff" && query.data && !query.data.has_previous_version) {
      setFreeformMode("preview");
    }
  }, [freeformMode, query.data]);

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
      setSuccessOpen(true);
    } catch {
      // mutation.error surfaced below.
    }
  }

  function handleAcceptAllNew() {
    discardPreviousMutation.mutate(undefined, {
      onSuccess: () => setFreeformMode("edit"),
    });
  }

  function handleRestoreAllPrevious() {
    restorePreviousMutation.mutate(undefined, {
      onSuccess: () => setFreeformMode("edit"),
    });
  }

  async function handleApplyMerged(merged: string) {
    try {
      await mutation.mutateAsync({
        free_form_markdown: merged,
        objective: query.data?.objective ?? "",
        counterparty_profile: query.data?.counterparty_profile ?? "",
        anticipated_topics: query.data?.anticipated_topics ?? "",
        anticipated_objections: query.data?.anticipated_objections ?? "",
        talking_points: query.data?.talking_points ?? "",
        red_lines: query.data?.red_lines ?? "",
      });
      discardPreviousMutation.mutate(undefined, {
        onSuccess: () => setFreeformMode("edit"),
      });
    } catch {
      // mutation.error surfaced below.
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

  // Mirror error to toast for parity with prior behavior (a11y live region).
  useEffect(() => {
    if (saveError) toast.error(saveError);
  }, [saveError]);

  const saveLabel = mutation.isPending
    ? t("playbook.save.saving")
    : savedAt
      ? t("playbook.save.saved")
      : t("playbook.save.idle");

  const dirty = !!query.data && draft !== query.data.free_form_markdown;
  // Save is always rendered now — Sean's feedback: the button disappearing on
  // mode switch felt abrupt. We just disable when there's nothing to save or
  // the user is browsing preview/diff.
  const saveEnabled = freeformMode === "edit" && dirty && !mutation.isPending;

  return (
    <>
      <Pane
        data-testid="playbook-pane"
        title={t("playbook.heading")}
        accent="var(--color-primary)"
        badge={<AiDraftChip label={t("playbook.aiDraftBadge")} />}
        actions={
          <div className="flex items-center gap-2">
            <SubModeToggle
              value={freeformMode}
              onChange={setFreeformMode}
              showDiff={query.data?.has_previous_version === true}
              labels={{
                edit: t("playbook.freeform.editTab"),
                preview: t("playbook.freeform.previewTab"),
                diff: t("playbook.diff.tab"),
              }}
            />
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={handleSave}
              disabled={!saveEnabled}
              data-testid="playbook-save-button"
              className={cn(
                "h-7 px-3 text-[12px] font-medium",
                // Disabled state stays tinted with Aura secondary (no grey) so
                // the button keeps its visual identity even when idle. Save
                // sits next to the primary-tinted SubModeToggle, so using
                // secondary here keeps the two affordances visually distinct.
                !saveEnabled &&
                  "bg-(--color-secondary)/20 text-(--color-secondary-foreground) opacity-100",
              )}
            >
              {dirty && freeformMode === "edit" && (
                <span
                  aria-hidden
                  data-testid="playbook-dirty-dot"
                  className="mr-1.5 inline-block size-1.5 rounded-full bg-current"
                />
              )}
              {saveLabel}
            </Button>
          </div>
        }
        bodyClassName="px-3.5 py-3.5"
      >
        <SpicyReveal revealKey={meetingId} className="space-y-4">
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
            {freeformMode === "edit" && (
              <textarea
                id="playbook-freeform"
                aria-label={t("playbook.freeform.label")}
                className={TEXTAREA_CLASSNAME}
                placeholder={t("playbook.freeform.placeholder")}
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  setSavedAt(null);
                }}
                rows={12}
              />
            )}
            {freeformMode === "preview" && <MarkdownPreview source={draft} />}
            {freeformMode === "diff" && query.data?.has_previous_version === true && (
              <PlaybookDiffViewer
                previous={query.data.previous_free_form_markdown ?? ""}
                current={query.data.free_form_markdown}
                decisions={diffDecisions}
                onDecisionsChange={setDiffDecisions}
                onAcceptAllNew={handleAcceptAllNew}
                onRestoreAllPrevious={handleRestoreAllPrevious}
                onApplyMerged={handleApplyMerged}
                isPending={
                  discardPreviousMutation.isPending ||
                  restorePreviousMutation.isPending ||
                  mutation.isPending
                }
              />
            )}
          </div>
        </SpicyReveal>

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

      <SuccessResultOverlay
        open={successOpen}
        onClose={() => setSuccessOpen(false)}
        title={t("playbook.save.success_title")}
        subtitle={t("playbook.save.success_subtitle")}
        autoDismissMs={2200}
      />
    </>
  );
}
