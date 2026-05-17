/**
 * PlaybookDiffViewer tests — slice-23 task 4.2.
 *
 * Covers design D4 (line-level diff via jsdiff) + D5 (per-hunk cherry-pick
 * accumulates into local state, then a single "apply merged" call).
 *
 * Assertions verify:
 *   - Renders one hunk per ChangeObject from diff.diffLines
 *   - "全部採用新版" / Accept-all calls `onAcceptAllNew` once
 *   - "全部回到舊版" / Restore-all calls `onRestoreAllPrevious` once
 *   - "套用挑選" is initially disabled (no per-hunk decisions made yet)
 *   - After flipping a per-hunk choice + clicking apply, the merged
 *     markdown built from the user's decisions is sent via `onApplyMerged`
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { PlaybookDiffViewer, type HunkDecisions } from "./playbook-diff-viewer";

const previousMarkdown = ["# Title", "", "line a", "line b", "line c"].join("\n");
const currentMarkdown = ["# Title", "", "line a", "line b NEW", "line c"].join("\n");

beforeEach(() => {
  // Reset i18n mock state between tests if needed (i18next is initialized globally).
});

afterEach(() => {
  cleanup();
});

// Gemini PR #36 review #4: the viewer is now controlled — `decisions`
// and `onDecisionsChange` are owned by the parent (PlaybookPane) so
// cherry-pick progress survives sub-mode switches. Tests that don't
// care about state mutation pass empty + noop; tests that exercise
// hunk clicks use this stateful wrapper.
function StatefulDiffViewer(
  props: Omit<React.ComponentProps<typeof PlaybookDiffViewer>, "decisions" | "onDecisionsChange">,
) {
  const [decisions, setDecisions] = useState<HunkDecisions>({});
  return <PlaybookDiffViewer {...props} decisions={decisions} onDecisionsChange={setDecisions} />;
}

describe("PlaybookDiffViewer", () => {
  test("renders a replace hunk pairing the previous + new sides into one logical block", () => {
    render(
      <StatefulDiffViewer
        previous={previousMarkdown}
        current={currentMarkdown}
        onAcceptAllNew={() => undefined}
        onRestoreAllPrevious={() => undefined}
        onApplyMerged={() => undefined}
      />,
    );

    // The fixture changes "line b" to "line b NEW" — an in-place
    // replacement. The viewer SHALL pair the adjacent remove + add into
    // a single replace hunk, not render them as two independent hunks.
    const replaceHunks = screen.getAllByTestId("diff-hunk-replace");
    expect(replaceHunks.length).toBe(1);
    // The single replace hunk renders both sides for visual context.
    const replaceHunk = replaceHunks[0]!;
    expect(replaceHunk.textContent ?? "").toContain("line b");
    expect(replaceHunk.textContent ?? "").toContain("line b NEW");
  });

  test("'accept all new' button invokes onAcceptAllNew once", async () => {
    const onAcceptAllNew = mock(() => undefined);
    const user = userEvent.setup();

    render(
      <StatefulDiffViewer
        previous={previousMarkdown}
        current={currentMarkdown}
        onAcceptAllNew={onAcceptAllNew}
        onRestoreAllPrevious={() => undefined}
        onApplyMerged={() => undefined}
      />,
    );

    await user.click(screen.getByTestId("diff-accept-all-new"));
    expect(onAcceptAllNew).toHaveBeenCalledTimes(1);
  });

  test("'restore all previous' button invokes onRestoreAllPrevious once", async () => {
    const onRestoreAllPrevious = mock(() => undefined);
    const user = userEvent.setup();

    render(
      <StatefulDiffViewer
        previous={previousMarkdown}
        current={currentMarkdown}
        onAcceptAllNew={() => undefined}
        onRestoreAllPrevious={onRestoreAllPrevious}
        onApplyMerged={() => undefined}
      />,
    );

    await user.click(screen.getByTestId("diff-restore-all-previous"));
    expect(onRestoreAllPrevious).toHaveBeenCalledTimes(1);
  });

  test("'apply merged' is disabled until every change hunk has an explicit decision", () => {
    render(
      <StatefulDiffViewer
        previous={previousMarkdown}
        current={currentMarkdown}
        onAcceptAllNew={() => undefined}
        onRestoreAllPrevious={() => undefined}
        onApplyMerged={() => undefined}
      />,
    );

    // No decisions yet → apply disabled.
    const applyBtn = screen.getByTestId("diff-apply-merged");
    expect(applyBtn.hasAttribute("disabled")).toBe(true);

    // Fixture is one replace hunk → one outstanding decision.
    const hint = screen.getByTestId("diff-undecided-hint");
    expect(hint.textContent ?? "").toMatch(/1/);
  });

  test("deciding 'use_previous' on the replace hunk enables apply and restores the old line", async () => {
    const onApplyMerged = mock((_merged: string) => undefined);
    const user = userEvent.setup();

    render(
      <StatefulDiffViewer
        previous={previousMarkdown}
        current={currentMarkdown}
        onAcceptAllNew={() => undefined}
        onRestoreAllPrevious={() => undefined}
        onApplyMerged={onApplyMerged}
      />,
    );

    // The single replace hunk has one pair of buttons; clicking
    // "use_previous" picks the old side and drops the new side.
    const decideBtn = screen.getAllByTestId("diff-decide-use-previous")[0];
    expect(decideBtn).toBeDefined();
    await user.click(decideBtn);

    // All decided → apply enabled, hint disappears.
    const applyBtn = screen.getByTestId("diff-apply-merged");
    expect(applyBtn.hasAttribute("disabled")).toBe(false);
    expect(screen.queryByTestId("diff-undecided-hint")).toBeNull();

    await user.click(applyBtn);

    expect(onApplyMerged).toHaveBeenCalledTimes(1);
    const merged = (onApplyMerged.mock.calls[0] as [string])[0];
    // The merged result should contain "line b" (restored) and NOT "line b NEW".
    expect(merged.includes("line b\n")).toBe(true);
    expect(merged.includes("line b NEW")).toBe(false);
  });
});
