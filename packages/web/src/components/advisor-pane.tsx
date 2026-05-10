/**
 * AdvisorPane — slice-9 right-column TacticalAdvisor surface.
 *
 * Three vertical sections per design.md Decision 8:
 *   1. ChatMessageList (top, scrolling) — persisted history + virtual
 *      in-flight bubbles
 *   2. Get Advice button (middle) — only rendered when phase === "in_progress"
 *   3. ChatInput (bottom) — textarea + Send, also only when in_progress
 *
 * Outside `in_progress`, the input controls hide but history bubbles
 * remain visible so the user can review past conversation.
 *
 * In-flight advice is rendered as two virtual ChatMessage bubbles
 * (user + advisor) appended to the persisted list. On `advice_done` the
 * route invalidates the React Query cache; the refetched response
 * brings the persisted pair into messages and the virtual pair vanishes.
 */

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { UseMeetingSessionResult } from "../hooks/use-meeting-session";
import type { ChatMessage } from "../lib/chat-api";
import { localizedErrorMessage } from "../lib/i18n-errors";
import { ChatInput } from "./chat-input";
import { ChatMessageList } from "./chat-message-list";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export interface AdvisorPaneProps {
  session: UseMeetingSessionResult;
  meDisplayName: string;
}

const _IN_FLIGHT_USER_ID = "__inflight_user__";
const _IN_FLIGHT_ADVISOR_ID = "__inflight_advisor__";

export function AdvisorPane({ session, meDisplayName }: AdvisorPaneProps) {
  const { t } = useTranslation();
  const phase = session.state.phase;
  const isLive = phase === "in_progress";
  const advisor = session.state.advisor;
  const inFlight = advisor.inFlight;
  const isStreaming = inFlight?.status === "streaming";

  // Combine persisted messages with the in-flight virtual bubbles. The
  // virtual user bubble shows the user's typed content immediately so the
  // UI doesn't feel laggy while waiting for the first advice token. The
  // virtual advisor bubble grows as `advice_chunk` frames arrive; while
  // empty it shows the localised "thinking…" placeholder.
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

  // Retry for a failed in-flight: resend via the original source path.
  const _retry = () => {
    if (inFlight === null || !isLive) return;
    if (inFlight.source === "chatbox") {
      session.sendChatMessage(inFlight.userContent);
    } else {
      session.requestAdvice();
    }
  };

  return (
    <Card data-testid="advisor-pane" className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>{t("meetings.advisor.heading")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden">
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

        {/* Failed in-flight: surface a retry button (only meaningful in_progress). */}
        {inFlight?.status === "failed" && isLive ? (
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
        ) : null}

        {isLive ? (
          <>
            <Button
              type="button"
              data-testid="get-advice-button"
              onClick={() => session.requestAdvice()}
              disabled={isStreaming}
            >
              {t("meetings.advisor.getAdviceButton")}
            </Button>
            <ChatInput onSend={session.sendChatMessage} disabled={isStreaming} />
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
