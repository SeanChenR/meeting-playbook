/**
 * RecordingModeSelector — slice-27 (single-channel-recording-entry) task 5.1.
 *
 * Renders the pre-meeting recording-mode radio group. Two mutually-exclusive
 * options, default `dual`, hides the `HeadphonesHint` when `single` is
 * chosen (the parent route reads `value` to drive that visibility).
 *
 * Per design.md D6 — "Selector 元件擺 MetadataCard 內、Start Meeting button
 * 上方" — and spec ADDED requirement "Pre-flight recording mode selector
 * chooses dual-channel or single-channel capture".
 *
 * Built on native `<input type="radio">` (no new shadcn dependency) so the
 * surface area stays small. Visual styling matches the design system
 * tokens (`--color-primary`, `--color-border`, `--color-muted-foreground`).
 * No emoji per project UI standards.
 */

import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { RecordingMode } from "../lib/session-ws";
import { cn } from "../lib/utils";

export interface RecordingModeSelectorProps {
  /** Currently selected mode (controlled). */
  value: RecordingMode;
  /** Called with the new mode when the user picks the other radio. */
  onChange: (mode: RecordingMode) => void;
  /** When true, both radios are disabled (e.g. session already starting). */
  disabled?: boolean;
}

export function RecordingModeSelector({
  value,
  onChange,
  disabled = false,
}: RecordingModeSelectorProps) {
  const { t } = useTranslation();
  const groupName = useId();
  const dualId = `${groupName}-dual`;
  const singleId = `${groupName}-single`;

  return (
    <fieldset
      data-testid="recording-mode-selector"
      aria-label={t("meetings.session.recordingMode.label")}
      className="rounded-md border border-(--color-border) bg-(--color-card) p-3"
    >
      <legend className="px-1 text-xs font-medium uppercase tracking-wide text-(--color-muted-foreground)">
        {t("meetings.session.recordingMode.label")}
      </legend>
      <div className="mt-2 flex flex-col gap-2">
        <ModeOption
          id={dualId}
          name={groupName}
          mode="dual"
          checked={value === "dual"}
          disabled={disabled}
          onSelect={onChange}
          label={t("meetings.session.recordingMode.dual")}
          helper={t("meetings.session.recordingMode.dualHelper")}
          testId="recording-mode-dual"
        />
        <ModeOption
          id={singleId}
          name={groupName}
          mode="single"
          checked={value === "single"}
          disabled={disabled}
          onSelect={onChange}
          label={t("meetings.session.recordingMode.single")}
          helper={t("meetings.session.recordingMode.singleHelper")}
          testId="recording-mode-single"
        />
      </div>
    </fieldset>
  );
}

interface ModeOptionProps {
  id: string;
  name: string;
  mode: RecordingMode;
  checked: boolean;
  disabled: boolean;
  onSelect: (mode: RecordingMode) => void;
  label: string;
  helper: string;
  testId: string;
}

function ModeOption({
  id,
  name,
  mode,
  checked,
  disabled,
  onSelect,
  label,
  helper,
  testId,
}: ModeOptionProps) {
  return (
    <label
      htmlFor={id}
      className={cn(
        "flex cursor-pointer items-start gap-2.5 rounded-md border border-(--color-border) p-2.5 text-sm",
        "hover:bg-(--color-muted)/40",
        checked && "border-(--color-primary)/60 bg-(--color-primary)/5",
        disabled && "cursor-not-allowed opacity-60 hover:bg-transparent",
      )}
    >
      <input
        id={id}
        data-testid={testId}
        type="radio"
        name={name}
        value={mode}
        checked={checked}
        disabled={disabled}
        onChange={() => onSelect(mode)}
        className="mt-0.5 size-4 accent-(--color-primary)"
      />
      <span className="flex flex-col gap-0.5">
        <span className="font-medium text-(--color-foreground)">{label}</span>
        <span data-testid={`${testId}-helper`} className="text-xs text-(--color-muted-foreground)">
          {helper}
        </span>
      </span>
    </label>
  );
}
