/**
 * TranscriptPane — chronological transcript chunks for a meeting session.
 *
 * Per spec meeting-session ADDED requirement "TranscriptPane renders chunks
 * with the meeting's me display name". For slice-6 every chunk has
 * `speaker = "me"`; the layout already accommodates a future "counterparty"
 * speaker (slice-7) by reading `chunk.speaker` and tagging via data attribute
 * for CSS targeting.
 *
 * NO emojis (per UI feedback memory). Visual polish comes in the UI overhaul.
 */

import { useTranslation } from "react-i18next";
import type { TranscriptChunkMessage } from "../lib/session-ws";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "../lib/utils";

interface TranscriptPaneProps {
  chunks: TranscriptChunkMessage[];
  meDisplayName: string;
  counterpartyDisplayName: string;
}

function _speakerLabel(
  chunk: TranscriptChunkMessage,
  meDisplayName: string,
  counterpartyDisplayName: string,
): string {
  if (chunk.speaker === "me") return meDisplayName;
  if (chunk.speaker === "counterparty") return counterpartyDisplayName;
  return chunk.speaker;
}

function _formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export function TranscriptPane({
  chunks,
  meDisplayName,
  counterpartyDisplayName,
}: TranscriptPaneProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("meetings.session.transcriptHeading")}</CardTitle>
      </CardHeader>
      <CardContent>
        {chunks.length === 0 ? (
          <div
            data-testid="transcript-empty"
            className="py-8 text-center text-sm text-(--color-muted-foreground)"
          >
            {t("meetings.session.transcriptEmpty")}
          </div>
        ) : (
          <ol className="space-y-3">
            {chunks.map((chunk, idx) => (
              <li
                key={`${chunk.started_at}-${idx}`}
                data-testid="transcript-chunk"
                data-speaker={chunk.speaker}
                className={cn(
                  // Slice-7 visual: each chunk gets a 4px left accent
                  // border (counterparty primary, me secondary/muted) and
                  // body text in default text-foreground (NOT colored).
                  "rounded-md border-l-4 bg-(--color-card) p-3 text-sm",
                  chunk.speaker === "counterparty"
                    ? "border-l-(--color-primary)"
                    : "border-l-(--color-muted-foreground)",
                )}
              >
                <div className="mb-1 flex items-center gap-2 text-xs text-(--color-muted-foreground)">
                  <span className="font-medium">
                    {_speakerLabel(chunk, meDisplayName, counterpartyDisplayName)}
                  </span>
                  <span aria-hidden>·</span>
                  <span>{_formatTime(chunk.started_at)}</span>
                </div>
                <p className="whitespace-pre-wrap text-(--color-foreground)">{chunk.text}</p>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
