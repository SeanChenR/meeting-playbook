/**
 * ThemeProvider tests — slice ui-overhaul-claude-design task 1.2.
 *
 * Covers the four scenarios from spec ui-design-system requirement
 * "ThemeProvider SHALL persist user choice and expose a typed Context":
 *   (a) no localStorage + system light → resolved=light + data-theme=light
 *   (b) setTheme("dark") → localStorage="dark" + data-theme="dark"
 *   (c) matchMedia change re-resolves when theme === "system"
 *   (d) corrupted localStorage falls back to "system" without throwing
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, cleanup, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";

import { ThemeProvider, useTheme } from "./theme-provider";

// happy-dom doesn't ship a working matchMedia implementation by default —
// install a controllable stub so we can simulate prefers-color-scheme.
type MqlListener = (event: { matches: boolean }) => void;

interface FakeMql {
  matches: boolean;
  media: string;
  listeners: Set<MqlListener>;
  addEventListener: (type: "change", listener: MqlListener) => void;
  removeEventListener: (type: "change", listener: MqlListener) => void;
}

function _installMatchMediaStub(initialPrefersDark: boolean): {
  mql: FakeMql;
  fire: (prefersDark: boolean) => void;
} {
  const mql: FakeMql = {
    matches: initialPrefersDark,
    media: "(prefers-color-scheme: dark)",
    listeners: new Set(),
    addEventListener: (_type, listener) => {
      mql.listeners.add(listener);
    },
    removeEventListener: (_type, listener) => {
      mql.listeners.delete(listener);
    },
  };
  // @ts-expect-error — overriding for tests
  window.matchMedia = (_query: string) => mql;
  const fire = (prefersDark: boolean) => {
    mql.matches = prefersDark;
    for (const l of mql.listeners) {
      l({ matches: prefersDark });
    }
  };
  return { mql, fire };
}

function _wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(cleanup);

describe("ThemeProvider", () => {
  test("(a) no localStorage + system light → resolved=light + data-theme=light", () => {
    _installMatchMediaStub(/* initialPrefersDark */ false);

    const { result } = renderHook(() => useTheme(), { wrapper: _wrapper });

    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  test("(b) setTheme('dark') writes localStorage + flips data-theme", async () => {
    _installMatchMediaStub(false);

    function _Probe() {
      const { theme, resolved, setTheme } = useTheme();
      return (
        <div>
          <span data-testid="theme">{theme}</span>
          <span data-testid="resolved">{resolved}</span>
          <button type="button" onClick={() => setTheme("dark")} data-testid="to-dark">
            dark
          </button>
        </div>
      );
    }

    render(
      <ThemeProvider>
        <_Probe />
      </ThemeProvider>,
    );

    await userEvent.click(screen.getByTestId("to-dark"));

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(screen.getByTestId("resolved").textContent).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("mp-theme")).toBe("dark");
  });

  test("(c) matchMedia change re-resolves when theme === 'system'", () => {
    const { fire } = _installMatchMediaStub(false); // start light

    const { result } = renderHook(() => useTheme(), { wrapper: _wrapper });
    expect(result.current.resolved).toBe("light");

    // OS preference flips to dark while theme stays "system".
    act(() => fire(true));

    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  test("(d) corrupted localStorage falls back to 'system' without throwing", () => {
    _installMatchMediaStub(false);
    window.localStorage.setItem("mp-theme", "purple");

    expect(() => {
      renderHook(() => useTheme(), { wrapper: _wrapper });
    }).not.toThrow();

    const { result } = renderHook(() => useTheme(), { wrapper: _wrapper });
    expect(result.current.theme).toBe("system");
  });
});
