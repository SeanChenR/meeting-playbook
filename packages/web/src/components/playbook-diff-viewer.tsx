/**
 * PlaybookDiffViewer — slice-23 task 4.2.
 *
 * Renders a line-level visual diff between the previous-version snapshot
 * (`previous_free_form_markdown`) and the current draft
 * (`free_form_markdown`). Per design D4 the diff is computed
 * client-side using `diff.diffLines` (jsdiff).
 *
 * Three global action buttons:
 *   - "Accept all new"     → onAcceptAllNew    (calls discard_previous)
 *   - "Restore all previous" → onRestoreAllPrevious (calls restore_previous)
 *   - "Apply cherry-pick"  → onApplyMerged(mergedMarkdown)
 *
 * Per-hunk cherry-pick UX (Sean revision 2): raw `diffLines` returns
 * adjacent `removed` + `added` runs for any in-place replacement. The
 * raw sequence is post-processed into "logical hunks" so a replacement
 * shows up as ONE hunk (red block above, purple block below, ONE pair
 * of decision buttons). Pure insertions and pure deletions stay as
 * single-color hunks, also with one pair of buttons.
 *
 * Every change hunk REQUIRES an explicit decision before "Apply
 * cherry-pick" enables — no implicit default. The Apply button is
 * disabled while any change hunk remains undecided and a hint surfaces
 * the outstanding count.
 *
 * The component is pure presentation — it does NOT call mutations
 * directly. The parent (playbook-pane) wires the three callbacks to
 * mutations from `playbook-api.ts`.
 */

import { diffLines } from "diff";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

// Per-hunk explicit decision. Undefined = undecided (Apply stays disabled).
export type HunkDecision = "use_new" | "use_previous";
export type HunkDecisions = Record<number, HunkDecision>;

export interface PlaybookDiffViewerProps {
  previous: string;
  current: string;
  /**
   * Controlled `decisions` map — lifted to the parent (PlaybookPane) so
   * the user's cherry-pick progress survives switching to Edit / Preview
   * sub-modes (which unmount this component). The parent resets the map
   * when the underlying playbook changes (new regenerate → new snapshot).
   */
  decisions: HunkDecisions;
  onDecisionsChange: (decisions: HunkDecisions) => void;
  onAcceptAllNew: () => void;
  onRestoreAllPrevious: () => void;
  onApplyMerged: (mergedMarkdown: string) => void;
  isPending?: boolean;
}

// Logical hunk — what the user actually decides on.
//
//   "common"  → unchanged context (no decision, always included)
//   "added"   → pure insertion (no matching previous side)
//   "removed" → pure deletion (no matching new side)
//   "replace" → previous block was rewritten to new block; one decision
//               picks between the two sides
type LogicalHunk =
  | { kind: "common"; index: number; value: string }
  | { kind: "added"; index: number; addedValue: string }
  | { kind: "removed"; index: number; removedValue: string }
  | { kind: "replace"; index: number; removedValue: string; addedValue: string };

// Walk raw `diffLines` output and pair adjacent removed→added runs into
// "replace" hunks. Standalone added or removed runs stay as such.
function buildLogicalHunks(previous: string, current: string): LogicalHunk[] {
  const raw = diffLines(previous, current);
  const out: LogicalHunk[] = [];
  let nextIndex = 0;
  let i = 0;
  while (i < raw.length) {
    const c = raw[i]!;
    if (!c.added && !c.removed) {
      out.push({ kind: "common", index: nextIndex++, value: c.value });
      i += 1;
      continue;
    }
    if (c.removed) {
      // Look ahead — if the next entry is an added run, pair them as
      // a single "replace" hunk so the user makes one decision.
      const next = raw[i + 1];
      if (next?.added) {
        out.push({
          kind: "replace",
          index: nextIndex++,
          removedValue: c.value,
          addedValue: next.value,
        });
        i += 2;
        continue;
      }
      out.push({ kind: "removed", index: nextIndex++, removedValue: c.value });
      i += 1;
      continue;
    }
    // c.added without a preceding removed — pure insertion.
    out.push({ kind: "added", index: nextIndex++, addedValue: c.value });
    i += 1;
  }
  return out;
}

// Build the merged markdown from the per-hunk decisions.
//
//   common  → always included
//   added + use_new      → include addedValue
//   added + use_previous → drop (revert insertion)
//   removed + use_new      → drop (accept deletion)
//   removed + use_previous → re-include removedValue
//   replace + use_new      → addedValue
//   replace + use_previous → removedValue
//
// Defensively treats undecided change hunks as "use_new" so the function
// never crashes if the Apply gate is bypassed.
function buildMerged(hunks: LogicalHunk[], decisions: HunkDecisions): string {
  const parts: string[] = [];
  for (const hunk of hunks) {
    if (hunk.kind === "common") {
      parts.push(hunk.value);
      continue;
    }
    const decision = decisions[hunk.index] ?? "use_new";
    if (hunk.kind === "added") {
      if (decision === "use_new") parts.push(hunk.addedValue);
      continue;
    }
    if (hunk.kind === "removed") {
      if (decision === "use_previous") parts.push(hunk.removedValue);
      continue;
    }
    // replace
    parts.push(decision === "use_new" ? hunk.addedValue : hunk.removedValue);
  }
  return parts.join("");
}

export function PlaybookDiffViewer({
  previous,
  current,
  decisions,
  onDecisionsChange,
  onAcceptAllNew,
  onRestoreAllPrevious,
  onApplyMerged,
  isPending = false,
}: PlaybookDiffViewerProps) {
  const { t } = useTranslation();

  const hunks = useMemo<LogicalHunk[]>(
    () => buildLogicalHunks(previous, current),
    [previous, current],
  );

  const changeHunks = useMemo(() => hunks.filter((h) => h.kind !== "common"), [hunks]);
  const undecidedCount = changeHunks.filter((h) => decisions[h.index] === undefined).length;
  const allDecided = changeHunks.length > 0 && undecidedCount === 0;

  function setHunkDecision(index: number, decision: HunkDecision): void {
    onDecisionsChange({ ...decisions, [index]: decision });
  }

  function handleApplyMerged(): void {
    const merged = buildMerged(hunks, decisions);
    onApplyMerged(merged);
  }

  return (
    <div className="space-y-3" data-testid="playbook-diff-viewer">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="primary"
          data-testid="diff-accept-all-new"
          disabled={isPending}
          onClick={onAcceptAllNew}
        >
          {t("playbook.diff.acceptAllNew")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid="diff-restore-all-previous"
          disabled={isPending}
          onClick={onRestoreAllPrevious}
        >
          {t("playbook.diff.restoreAllPrevious")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          data-testid="diff-apply-merged"
          disabled={!allDecided || isPending}
          onClick={handleApplyMerged}
        >
          {t("playbook.diff.applyMerged")}
        </Button>
        {undecidedCount > 0 && (
          <span
            data-testid="diff-undecided-hint"
            className="text-xs text-(--color-muted-foreground)"
          >
            {t("playbook.diff.undecidedHint", { count: undecidedCount })}
          </span>
        )}
      </div>

      {hunks.length === 0 || (hunks.length === 1 && hunks[0]?.kind === "common") ? (
        <p className="text-sm text-(--color-muted-foreground)" data-testid="diff-empty-hint">
          {t("playbook.diff.emptyHint")}
        </p>
      ) : (
        <div
          className="space-y-1 overflow-x-auto rounded-md border border-(--color-border) bg-(--color-card) p-3 text-sm leading-relaxed font-mono"
          data-testid="diff-hunks-container"
        >
          {hunks.map((hunk) => {
            if (hunk.kind === "common") {
              return (
                <pre
                  key={hunk.index}
                  data-testid="diff-hunk-common"
                  className="whitespace-pre-wrap text-(--color-foreground)"
                >
                  {hunk.value}
                </pre>
              );
            }
            const decision = decisions[hunk.index];
            return (
              <div
                key={hunk.index}
                data-testid={`diff-hunk-${hunk.kind}`}
                className="my-1 space-y-1 rounded border border-(--color-border)/40 p-1"
              >
                {(hunk.kind === "removed" || hunk.kind === "replace") && (
                  <pre
                    data-testid="diff-side-previous"
                    className="whitespace-pre-wrap bg-(--color-destructive)/10 px-1 text-(--color-foreground)"
                  >
                    <del className="no-underline opacity-80">{hunk.removedValue}</del>
                  </pre>
                )}
                {(hunk.kind === "added" || hunk.kind === "replace") && (
                  <pre
                    data-testid="diff-side-new"
                    className="whitespace-pre-wrap bg-(--color-accent)/10 px-1 text-(--color-foreground)"
                  >
                    <ins className="no-underline">{hunk.addedValue}</ins>
                  </pre>
                )}
                <div className="flex justify-end gap-1 px-1">
                  <DecisionChip
                    selected={decision === "use_new"}
                    onClick={() => setHunkDecision(hunk.index, "use_new")}
                    data-testid="diff-decide-use-new"
                    label={t("playbook.diff.useNew")}
                  />
                  <DecisionChip
                    selected={decision === "use_previous"}
                    onClick={() => setHunkDecision(hunk.index, "use_previous")}
                    data-testid="diff-decide-use-previous"
                    label={t("playbook.diff.usePrevious")}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Inline decision chip used inside each diff hunk. Intentionally NOT
// the project `<Button>` component — that ships h-9 + hover-lift +
// shadow pump tuned for primary CTAs, which dominates a compact in-line
// hunk layout. This chip keeps consistent focus-visible + aria-pressed
// + disabled treatment so the a11y story matches the rest of the app.
interface DecisionChipProps {
  selected: boolean;
  onClick: () => void;
  label: string;
  "data-testid": string;
}

function DecisionChip({ selected, onClick, label, ...rest }: DecisionChipProps) {
  return (
    <button
      type="button"
      data-testid={rest["data-testid"]}
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "rounded border px-2 py-0.5 text-xs transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
        "disabled:cursor-not-allowed disabled:opacity-50",
        selected
          ? "border-(--color-primary) bg-(--color-primary) text-(--color-primary-foreground)"
          : "border-(--color-border) bg-(--color-card) text-(--color-foreground) hover:bg-(--color-muted)",
      )}
    >
      {label}
    </button>
  );
}
