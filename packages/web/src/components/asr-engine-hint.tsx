/**
 * AsrEngineHint — single-line inline alert telling the user which ASR engine
 * will run / is running for this meeting. Always visible when the meeting
 * detail page is mounted (refactor-meeting-detail-three-column third-round
 * review: Sean asked for an explicit cue showing which model is active).
 *
 * Reads `meeting.asr_provider` and maps to a human-readable display name.
 * If unknown, falls back to the raw id.
 */

import { Cpu } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Alert } from "./ui/alert";

export interface AsrEngineHintProps {
  /** Provider id from `meeting.asr_provider` (e.g. "whisper", "qwen3"). */
  provider: string | null | undefined;
}

function _displayName(provider: string | null | undefined): string {
  if (!provider) return "—";
  // Match the AsrProviderSelector option labels: keep short, brand-style names.
  const map: Record<string, string> = {
    whisper: "Whisper",
    "whisper-large-v3": "Whisper Large v3",
    qwen3: "Qwen3-ASR",
    "qwen3-asr": "Qwen3-ASR",
  };
  return map[provider] ?? provider;
}

export function AsrEngineHint({ provider }: AsrEngineHintProps) {
  const { t } = useTranslation();
  return (
    <Alert
      data-testid="asr-engine-hint"
      variant="default"
      role="status"
      className="flex items-center gap-3"
    >
      <Cpu className="size-4 shrink-0 text-(--color-primary)" strokeWidth={1.5} aria-hidden />
      <span className="flex-1 text-sm">
        {t("meetings.detail.asrEngineHint", { provider: _displayName(provider) })}
      </span>
    </Alert>
  );
}
