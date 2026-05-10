/**
 * ChatMessageList — chronological chat history for the AdvisorPane.
 *
 * Per spec tactical-advisor MODIFIED requirement "AdvisorPane renders
 * chat-style cards" + design.md Decision 8: user-role messages render
 * right-aligned, advisor-role messages render left-aligned with rendered
 * markdown. The list auto-scrolls to keep the latest message visible.
 *
 * NO emojis (per UI feedback memory).
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ChatMessage } from "../lib/chat-api";
import { MarkdownPreview } from "../lib/markdown-preview";
import { cn } from "../lib/utils";

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

  // Auto-scroll to bottom when the list grows OR the trailing message body
  // grows (for streaming token updates).
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
          <div
            key={m.id}
            data-testid="chat-bubble"
            data-role={m.role}
            className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                isUser ? "bg-primary text-primary-foreground" : "border border-border bg-card",
              )}
            >
              <div className="mb-1 flex items-center justify-between gap-2 text-xs opacity-70">
                <span>{isUser ? meDisplayName : t("meetings.advisor.advisorLabel")}</span>
                <span>{_formatTime(m.created_at)}</span>
              </div>
              {isUser ? (
                <p className="whitespace-pre-wrap break-words">{m.content}</p>
              ) : (
                <MarkdownPreview source={m.content} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
