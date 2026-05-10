/**
 * ChatInput — slice-9 chatbox input tests.
 *
 * Per spec tactical-advisor MODIFIED requirement scenarios:
 * - "Send button is disabled when textarea is empty"
 * - "Cmd+Enter in textarea sends a chat_message frame"
 */

import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChatInput } from "./chat-input";

afterEach(cleanup);

describe("ChatInput", () => {
  test("Send button is disabled when textarea is empty", () => {
    render(<ChatInput onSend={() => {}} disabled={false} />);
    const send = screen.getByTestId("chat-input-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
  });

  test("Send button enables once user types non-whitespace", () => {
    render(<ChatInput onSend={() => {}} disabled={false} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "X" } });
    const send = screen.getByTestId("chat-input-send") as HTMLButtonElement;
    expect(send.disabled).toBe(false);
  });

  test("disabled prop overrides — Send stays disabled even with content", () => {
    render(<ChatInput onSend={() => {}} disabled={true} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "X" } });
    const send = screen.getByTestId("chat-input-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
  });

  test("clicking Send calls onSend with trimmed content + clears textarea", () => {
    const onSend = mock(() => {});
    render(<ChatInput onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "  hello  " } });
    fireEvent.click(screen.getByTestId("chat-input-send"));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0]![0]).toBe("hello");
    expect(ta.value).toBe("");
  });

  test("Cmd+Enter (metaKey) calls onSend and clears textarea", () => {
    const onSend = mock(() => {});
    render(<ChatInput onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "X" } });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0]![0]).toBe("X");
    expect(ta.value).toBe("");
  });

  test("Ctrl+Enter (ctrlKey) also triggers send for non-macOS users", () => {
    const onSend = mock(() => {});
    render(<ChatInput onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "X" } });
    fireEvent.keyDown(ta, { key: "Enter", ctrlKey: true });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  test("plain Enter (no modifier) does NOT send — newline behavior", () => {
    const onSend = mock(() => {});
    render(<ChatInput onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("chat-input-textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "X" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });
});
