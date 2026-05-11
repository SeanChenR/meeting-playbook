/**
 * ChatBubble — slice ui-overhaul-claude-design task 6.3.
 *
 * Single chat message rendered as a one-sided bubble, matching the
 * design bundle's AdvisorPane:
 *   - role="user"      → right-aligned, --color-primary background,
 *                        primary-foreground text, asymmetric radius
 *                        (`rounded-lg rounded-br-sm`)
 *   - role="assistant" → left-aligned, --color-card background, 1px
 *                        border, asymmetric radius (`rounded-lg rounded-bl-sm`)
 *
 * Width capped at 85% of the container so long messages wrap naturally
 * without spanning the full pane.
 *
 * `data-testid="chat-bubble"` + `data-role` preserved so the existing
 * AdvisorPane tests still resolve.
 */

import type { ReactNode } from "react";
import { cn } from "../lib/utils";

export type ChatBubbleRole = "user" | "advisor";

export interface ChatBubbleProps {
  role: ChatBubbleRole;
  /** Header line — usually display name + timestamp. */
  header?: ReactNode;
  /** Message body. Accepts ReactNode so callers can render markdown. */
  children: ReactNode;
}

export function ChatBubble({ role, header, children }: ChatBubbleProps) {
  const isUser = role === "user";
  return (
    <div
      data-testid="chat-bubble"
      data-role={role}
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] px-3 py-2 text-sm leading-relaxed",
          isUser
            ? "rounded-lg rounded-br-sm bg-(--color-primary) text-(--color-primary-foreground)"
            : // Dark-mode --color-card is only 0.04 lightness above the page bg;
              // bumping to --color-muted (surface-2) lifts the bubble enough to
              // read while staying inside the surface family in light mode too.
              "rounded-lg rounded-bl-sm border border-(--color-border) bg-(--color-muted) text-(--color-foreground)",
        )}
      >
        {header && (
          <div className="mb-1 flex items-center justify-between gap-2 text-xs opacity-70">
            {header}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
