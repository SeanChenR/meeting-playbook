/**
 * ThemeProvider — slice ui-overhaul-claude-design task 1.2.
 *
 * Per `ui-design-system` spec requirement
 * "ThemeProvider SHALL persist user choice and expose a typed Context":
 *
 *   theme: "light" | "dark" | "system"   (raw user preference)
 *   resolved: "light" | "dark"            (after collapsing "system" against
 *                                          prefers-color-scheme)
 *   setTheme(t) — persists to localStorage.mp-theme
 *
 * `documentElement.setAttribute("data-theme", resolved)` flips the
 * `:root` / `[data-theme="dark"]` token blocks in `index.css`.
 *
 * Resilience:
 *   - Corrupted localStorage values fall back to "system" without throwing.
 *   - matchMedia listener responds to live OS preference changes when
 *     theme === "system".
 *   - SSR-style guards (`typeof window !== "undefined"`) keep this safe
 *     even though Vite app currently has no SSR — defensive for future.
 */

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
  theme: Theme;
  resolved: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const STORAGE_KEY = "mp-theme";
const VALID_THEMES: readonly Theme[] = ["light", "dark", "system"] as const;

const ThemeContext = createContext<ThemeContextValue | null>(null);

function _readStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw && (VALID_THEMES as readonly string[]).includes(raw)) {
      return raw as Theme;
    }
  } catch {
    // localStorage may throw in private-browsing modes; fall back silently.
  }
  return "system";
}

function _systemPreference(): ResolvedTheme {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function _resolve(theme: Theme): ResolvedTheme {
  return theme === "system" ? _systemPreference() : theme;
}

export interface ThemeProviderProps {
  children: ReactNode;
  /** Test seam — lets unit tests inject a starting preference without
   *  monkey-patching localStorage. Production always omits. */
  initialTheme?: Theme;
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => initialTheme ?? _readStoredTheme());
  const [resolved, setResolved] = useState<ResolvedTheme>(() => _resolve(theme));

  // Apply data-theme + recompute resolved whenever the user preference changes.
  useEffect(() => {
    const next = _resolve(theme);
    setResolved(next);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", next);
    }
  }, [theme]);

  // Persist preference. Failure (e.g. private mode quota exceeded) is silent.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Persistence is best-effort; theme still works in-session.
    }
  }, [theme]);

  // Live-react to OS preference changes ONLY when theme === "system".
  useEffect(() => {
    if (theme !== "system" || typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const next: ResolvedTheme = mql.matches ? "dark" : "light";
      setResolved(next);
      if (typeof document !== "undefined") {
        document.documentElement.setAttribute("data-theme", next);
      }
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolved, setTheme }),
    [theme, resolved, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  return ctx;
}
