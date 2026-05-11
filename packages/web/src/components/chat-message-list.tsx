/**
 * ChatMessageList — chronological chat history for the AdvisorPane.
 *
 * Phase 6 (task 6.3): per-message bubble extracted to `ChatBubble`. The
 * list keeps auto-scroll behaviour for streaming token updates.
 *
 * Existing API + data-testids preserved (`chat-message-list`,
 * `chat-bubble`, `data-role`).
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ChatMessage } from "../lib/chat-api";
import { MarkdownPreview } from "../lib/markdown-preview";
import { ChatBubble } from "./chat-bubble";

export interface ChatMessageListProps {
  messages: ChatMessage[];
  meDisplayName: string;
}

function _formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function ChatMessageList({ messages, meDisplayName }: ChatMessageListProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLDivElement | null>(null);

  const lastLen = messages.at(-1)?.content.length ?? 0;
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, lastLen]);

  if (messages.length === 0) return null;

  return (
    <div
      ref={listRef}
      data-testid="chat-message-list"
      className="flex flex-1 flex-col gap-2 overflow-y-auto"
    >
      {messages.map((m) => {
        const isUser = m.role === "user";
        return (
          <ChatBubble
            key={m.id}
            role={isUser ? "user" : "advisor"}
            header={
              <>
                <span>{isUser ? meDisplayName : t("meetings.advisor.advisorLabel")}</span>
                <span>{_formatTime(m.created_at)}</span>
              </>
            }
          >
            {isUser ? (
              <p className="break-words whitespace-pre-wrap">{m.content}</p>
            ) : (
              <MarkdownPreview source={m.content} />
            )}
          </ChatBubble>
        );
      })}
    </div>
  );
}
