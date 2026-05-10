/**
 * ChatInput — textarea + Send button for the chatbox follow-up.
 *
 * Per spec tactical-advisor MODIFIED requirement scenario "Cmd+Enter in
 * textarea sends a chat_message frame": Cmd+Enter (macOS) / Ctrl+Enter
 * triggers send; Send button is disabled when textarea is empty OR a
 * prior advice is mid-flight.
 */

import { type KeyboardEvent, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/button";

export interface ChatInputProps {
  onSend: (content: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");

  const trimmed = value.trim();
  const sendDisabled = disabled || trimmed.length === 0;

  const _send = useCallback(() => {
    if (sendDisabled) return;
    onSend(trimmed);
    setValue("");
  }, [sendDisabled, trimmed, onSend]);

  const _onKeyDown = useCallback(
    (ev: KeyboardEvent<HTMLTextAreaElement>) => {
      // Cmd+Enter (macOS) or Ctrl+Enter (Win/Linux) sends.
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        _send();
      }
    },
    [_send],
  );

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-end gap-2">
        <textarea
          data-testid="chat-input-textarea"
          value={value}
          onChange={(ev) => setValue(ev.target.value)}
          onKeyDown={_onKeyDown}
          placeholder={t("meetings.advisor.chatPlaceholder")}
          rows={2}
          className="min-h-[2.5rem] flex-1 resize-y rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <Button type="button" data-testid="chat-input-send" onClick={_send} disabled={sendDisabled}>
          {t("meetings.advisor.send")}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{t("meetings.advisor.cmdEnterHint")}</p>
    </div>
  );
}
