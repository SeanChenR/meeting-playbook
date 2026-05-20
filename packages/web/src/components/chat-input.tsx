/**
 * ChatInput — Claude Design v2 rounded pill input + icon send button.
 *
 * The bar is rendered as a single rounded container (textarea + icon button)
 * matching the transcript / advisor chunk shape. When `disabled === true`
 * the textarea + Send button stay visible but lose interactivity so users
 * can see the affordance is paused (e.g. when no live session, idle, or a
 * prior advice request is mid-flight).
 *
 * Cmd+Enter (macOS) / Ctrl+Enter still triggers send (spec contract).
 */

import { Send } from "lucide-react";
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";

export interface ChatInputProps {
  onSend: (content: string) => void;
  disabled: boolean;
  /** Optional seed pair: when its `key` changes, prefill `text` + focus. */
  seed?: { key: string | number; text: string } | null;
}

export function ChatInput({ onSend, disabled, seed = null }: ChatInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const lastSeedKey = useRef<string | number | null>(null);

  useEffect(() => {
    if (!seed) return;
    if (lastSeedKey.current === seed.key) return;
    lastSeedKey.current = seed.key;
    setValue(seed.text);
    queueMicrotask(() => {
      const el = taRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(seed.text.length, seed.text.length);
      }
    });
  }, [seed]);

  const trimmed = value.trim();
  const sendDisabled = disabled || trimmed.length === 0;

  const _send = useCallback(() => {
    if (sendDisabled) return;
    onSend(trimmed);
    setValue("");
  }, [sendDisabled, trimmed, onSend]);

  const _onKeyDown = useCallback(
    (ev: KeyboardEvent<HTMLTextAreaElement>) => {
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        _send();
      }
    },
    [_send],
  );

  return (
    <div className="flex flex-col gap-1">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl bg-(--color-card) px-3 py-2",
          "ring-1 ring-(--color-border)/60 transition-all",
          "focus-within:ring-2 focus-within:ring-(--color-primary)/45",
          disabled && "bg-(--color-muted)/40 opacity-70 cursor-not-allowed",
        )}
      >
        <textarea
          ref={taRef}
          data-testid="chat-input-textarea"
          value={value}
          onChange={(ev) => setValue(ev.target.value)}
          onKeyDown={_onKeyDown}
          disabled={disabled}
          placeholder={t("meetings.advisor.chatPlaceholder")}
          rows={1}
          className={cn(
            "min-h-[2rem] flex-1 resize-none bg-transparent px-1 py-1 text-sm leading-snug",
            "placeholder:text-(--color-muted-foreground)",
            "focus:outline-none disabled:cursor-not-allowed",
          )}
        />
        <button
          type="button"
          data-testid="chat-input-send"
          onClick={_send}
          disabled={sendDisabled}
          aria-label={t("meetings.advisor.send")}
          className={cn(
            "inline-flex size-8 shrink-0 items-center justify-center rounded-full",
            "bg-(--color-primary) text-(--color-primary-foreground) transition-all",
            "hover:bg-(--color-primary-hover) hover:scale-105",
            "disabled:bg-(--color-primary)/35 disabled:cursor-not-allowed",
            "disabled:hover:scale-100",
          )}
        >
          <Send size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>
      <p className="px-2 text-xs text-(--color-muted-foreground)">
        {t("meetings.advisor.cmdEnterHint")}
      </p>
    </div>
  );
}
