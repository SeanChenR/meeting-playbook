/**
 * AsrProviderSelector — slice-11 task 6.1.
 *
 * Replaces the read-only ASR engine label in the meeting metadata card with
 * a native `<select>` dropdown (no shadcn select component yet — fine per
 * Sean's "shadcn-first, magicui later" UI overhaul plan). Switching the
 * dropdown fires PATCH /api/meetings/{id} {asr_provider}; the change takes
 * effect on the NEXT WS connect (the live session keeps its connect-time
 * providers per slice-11 design Decision 1 — that's why we always show the
 * "Takes effect on the next meeting" hint).
 */

import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { type Meeting, usePatchMeetingMutation } from "../lib/meetings-api";

// Post asr-runtime-extraction (ADR-0027): only Qwen3 is a valid provider.
// The selector now renders a single-option dropdown so the affordance
// keeps its shape for future engines without leaking the retired Whisper
// option back into the UI.
const PROVIDER_VALUES = ["qwen3"] as const;
type ProviderValue = (typeof PROVIDER_VALUES)[number];

interface AsrProviderSelectorProps {
  meeting: Pick<Meeting, "id" | "asr_provider">;
}

export function AsrProviderSelector({ meeting }: AsrProviderSelectorProps) {
  const { t } = useTranslation();
  const mutation = usePatchMeetingMutation(meeting.id);

  const onChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value as ProviderValue;
    if (next === meeting.asr_provider) return;
    mutation.mutate({ asr_provider: next });
  };

  const errorCode =
    mutation.error && "errorCode" in mutation.error
      ? (mutation.error as { errorCode?: string }).errorCode
      : undefined;
  const errorMessage = errorCode ? localizedErrorMessage(errorCode, t) : null;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="font-medium">{t("meetings.detail.asrProviderLabel")}：</span>
        <select
          data-testid="asr-provider-selector"
          value={meeting.asr_provider}
          onChange={onChange}
          disabled={mutation.isPending}
          className="rounded-md border border-(--color-border) bg-(--color-background) px-2 py-1 text-sm"
        >
          {PROVIDER_VALUES.map((value) => (
            <option key={value} value={value}>
              Qwen3
            </option>
          ))}
        </select>
      </div>
      <span className="text-xs text-(--color-muted-foreground)">
        {t("meetings.detail.asrProviderSwitchHint")}
      </span>
      {errorMessage ? (
        <span className="text-xs text-(--color-destructive)">{errorMessage}</span>
      ) : null}
    </div>
  );
}
