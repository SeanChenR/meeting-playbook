/**
 * AdvisorPane — slice ui-overhaul-claude-design task 6.3.
 *
 * Re-skinned with the shared `Pane` shell. Per design bundle:
 *   - Body: `ChatMessageList` (extracted ChatBubble component, see 6.3)
 *   - Suggestion chips at the tail of the list when there's no in-flight
 *     advice (3 i18n keys: nextStep / realConcern / closing)
 *   - Click chip → seed the ChatInput textarea with that text + focus
 *   - Bottom input row: ChatInput + Get Advice button (when in_progress)
 *
 * Slice-9 chat persistence behaviour preserved verbatim (in-flight virtual
 * bubbles, advice_done cache invalidation, retry button on failed in-flight).
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMeetingSessionResult } from "../hooks/use-meeting-session";
import type { ChatMessage } from "../lib/chat-api";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { ChatInput } from "./chat-input";
import { ChatMessageList } from "./chat-message-list";
import { Pane } from "./pane";
import { Button } from "./ui/button";

export interface AdvisorPaneProps {
  session: UseMeetingSessionResult;
  meDisplayName: string;
}

const _IN_FLIGHT_USER_ID = "__inflight_user__";
const _IN_FLIGHT_ADVISOR_ID = "__inflight_advisor__";

const SUGGESTION_KEYS = [
  "meetings.advisor.suggestions.nextStep",
  "meetings.advisor.suggestions.realConcern",
  "meetings.advisor.suggestions.closing",
] as const;

export function AdvisorPane({ session, meDisplayName }: AdvisorPaneProps) {
  const { t } = useTranslation();
  const phase = session.state.phase;
  const isLive = phase === "in_progress";
  const advisor = session.state.advisor;
  const inFlight = advisor.inFlight;
  const isStreaming = inFlight?.status === "streaming";

  const [seed, setSeed] = useState<{ key: number; text: string } | null>(null);

  const renderedMessages: ChatMessage[] = useMemo(() => {
    if (inFlight === null) return advisor.messages;
    const meeting_id = advisor.messages[0]?.meeting_id ?? "__inflight__";
    const now = new Date().toISOString();
    const userBubble: ChatMessage = {
      id: _IN_FLIGHT_USER_ID,
      meeting_id,
      role: "user",
      content: inFlight.userContent,
      created_at: now,
    };
    const advisorContent =
      inFlight.status === "failed"
        ? localizedErrorMessage(inFlight.error?.code ?? "advisor.unknown", t)
        : inFlight.advisorTokens === ""
          ? t("meetings.advisor.thinking")
          : inFlight.advisorTokens;
    const advisorBubble: ChatMessage = {
      id: _IN_FLIGHT_ADVISOR_ID,
      meeting_id,
      role: "advisor",
      content: advisorContent,
      created_at: now,
    };
    return [...advisor.messages, userBubble, advisorBubble];
  }, [advisor.messages, inFlight, t]);

  const showEmptyState = renderedMessages.length === 0 && !isLive;
  // Suggestion chips appear when the chatbox is interactive (in_progress)
  // and nothing is mid-flight; lets the user jump-start a thread.
  const showSuggestions = isLive && inFlight === null;

  const _retry = () => {
    if (inFlight === null || !isLive) return;
    if (inFlight.source === "chatbox") {
      session.sendChatMessage(inFlight.userContent);
    } else {
      session.requestAdvice();
    }
  };

  return (
    <Pane
      data-testid="advisor-pane"
      title={t("meetings.advisor.heading")}
      accent="oklch(0.62 0.18 145)"
      bodyClassName="flex flex-col gap-3 p-3.5"
    >
      {showEmptyState ? (
        <div
          data-testid="advisor-pane-empty"
          className="flex flex-1 items-center justify-center text-sm text-(--color-muted-foreground)"
        >
          {t("meetings.advisor.emptyState")}
        </div>
      ) : (
        <ChatMessageList messages={renderedMessages} meDisplayName={meDisplayName} />
      )}

      {showSuggestions && (
        <div data-testid="advisor-suggestions" className="flex flex-wrap gap-1.5">
          {SUGGESTION_KEYS.map((key) => {
            const text = t(key);
            return (
              <button
                key={key}
                type="button"
                data-testid="advisor-suggestion-chip"
                onClick={() => setSeed({ key: Date.now(), text })}
                className="rounded-full border border-(--color-border) bg-(--color-muted)/50 px-2.5 py-1 text-xs font-medium text-(--color-muted-foreground) transition-colors hover:bg-(--color-muted) hover:text-(--color-foreground)"
              >
                {text}
              </button>
            );
          })}
        </div>
      )}

      {inFlight?.status === "failed" && isLive && (
        <div className="flex justify-end">
          <Button
            type="button"
            size="sm"
            variant="outline"
            data-testid="advice-retry-button"
            onClick={_retry}
          >
            {t("meetings.advisor.retry")}
          </Button>
        </div>
      )}

      {isLive && (
        <>
          <Button
            type="button"
            data-testid="get-advice-button"
            onClick={() => session.requestAdvice()}
            disabled={isStreaming}
            size="sm"
          >
            {t("meetings.advisor.getAdviceButton")}
          </Button>
          <ChatInput onSend={session.sendChatMessage} disabled={isStreaming} seed={seed} />
        </>
      )}
    </Pane>
  );
}
