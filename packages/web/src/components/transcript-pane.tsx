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
}

function _speakerLabel(chunk: TranscriptChunkMessage, meDisplayName: string): string {
  if (chunk.speaker === "me") return meDisplayName;
  if (chunk.speaker === "counterparty") return "對方";
  return chunk.speaker;
}

function _formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export function TranscriptPane({ chunks, meDisplayName }: TranscriptPaneProps) {
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
                  "rounded-md border p-3 text-sm",
                  chunk.speaker === "me"
                    ? "border-(--color-input) bg-(--color-card)"
                    : "border-(--color-border) bg-(--color-muted)",
                )}
              >
                <div className="mb-1 flex items-center justify-between text-xs text-(--color-muted-foreground)">
                  <span className="font-medium">{_speakerLabel(chunk, meDisplayName)}</span>
                  <span>{_formatTime(chunk.started_at)}</span>
                </div>
                <p className="whitespace-pre-wrap">{chunk.text}</p>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
