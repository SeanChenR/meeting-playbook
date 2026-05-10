/**
 * AdvisorPane — right-column TacticalAdvisor surface.
 *
 * Slice-8: replaces the slice-7 placeholder pane. Renders:
 * - history list of advice cards (oldest → newest), each rendered via
 *   MarkdownPreview so Vertex Flash's bullet markdown shows nicely
 * - "Get Advice" button at the bottom (slice-9 will add a chatbox above it)
 * - failed cards include a Retry button that re-issues request_advice
 *
 * When `session.state.phase !== "in_progress"`, the pane shows an empty
 * state and HIDES the Get Advice button — advice only makes sense while
 * the meeting is live (we need recent transcript chunks for context).
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { MarkdownPreview } from "../lib/markdown-preview";
import type { UseMeetingSessionResult } from "../hooks/use-meeting-session";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

export interface AdvisorPaneProps {
  session: UseMeetingSessionResult;
}

function _formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function AdvisorPane({ session }: AdvisorPaneProps) {
  const { t } = useTranslation();
  const requests = session.state.advisor.requests;
  const lastStatus = requests.at(-1)?.status;
  const isStreaming = lastStatus === "streaming";

  const listRef = useRef<HTMLDivElement | null>(null);
  // Auto-scroll the list to the latest card whenever a new card is added or
  // the streaming card grows. Cheap because the only thing that changes here
  // is `requests.length` + the current card's `tokens` length.
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [requests.length, requests.at(-1)?.tokens.length]);

  // Slice-08 round 2: keep history visible across phases. The "Get Advice"
  // button only makes sense while the meeting is live (we need recent
  // transcript chunks for context), but past advice cards stay readable
  // even after End — Sean asked for this so he can review the LLM output
  // post-meeting without losing it the moment he clicks End.
  const isLive = session.state.phase === "in_progress";
  const showEmptyState = !isLive && requests.length === 0;

  return (
    <section
      data-testid="advisor-pane"
      className="flex h-full flex-col gap-3 rounded-md border border-border bg-card p-4"
    >
      <header className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">{t("meetings.advisor.heading")}</h2>
      </header>

      {showEmptyState ? (
        <div
          data-testid="advisor-pane-empty"
          className="flex flex-1 items-center justify-center text-sm text-muted-foreground"
        >
          {t("meetings.advisor.emptyState")}
        </div>
      ) : (
        <>
          <div ref={listRef} className="flex flex-1 flex-col gap-3 overflow-y-auto">
            {requests.length === 0 ? (
              <div
                data-testid="advisor-pane-no-requests"
                className="flex flex-1 items-center justify-center text-sm text-muted-foreground"
              >
                {t("meetings.advisor.emptyState")}
              </div>
            ) : (
              requests.map((req) => (
                <Card
                  key={req.requestId}
                  data-testid="advice-card"
                  data-status={req.status}
                  className="p-3"
                >
                  <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {_formatTime(req.startedAt)} · {t("meetings.advisor.cardHeading")}
                    </span>
                    {req.status === "streaming" ? (
                      <span data-testid="advice-thinking">{t("meetings.advisor.thinking")}</span>
                    ) : null}
                  </div>
                  {req.status === "failed" ? (
                    <div className="space-y-2">
                      <p className="text-sm text-destructive">
                        {localizedErrorMessage(req.error?.code ?? "advisor.unknown", t)}
                      </p>
                      {/* Slice-08 round 2: surface the raw backend message
                          so Sean can debug from the UI without tailing logs.
                          Hidden when message is empty / equal to the code. */}
                      {req.error?.message && req.error.message !== req.error.code ? (
                        <p
                          data-testid="advice-failed-detail"
                          className="text-xs text-muted-foreground break-words"
                        >
                          {req.error.message}
                        </p>
                      ) : null}
                      {isLive ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          data-testid="advice-retry-button"
                          onClick={() => session.requestAdvice()}
                        >
                          {t("meetings.advisor.retry")}
                        </Button>
                      ) : null}
                    </div>
                  ) : (
                    <MarkdownPreview source={req.tokens} />
                  )}
                </Card>
              ))
            )}
          </div>
          {isLive ? (
            <Button
              type="button"
              data-testid="get-advice-button"
              onClick={() => session.requestAdvice()}
              disabled={isStreaming}
            >
              {t("meetings.advisor.getAdviceButton")}
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}
