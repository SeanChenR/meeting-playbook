/**
 * ThemeToggle — ui-overhaul-primitive-upgrade task 7 (Decision 4).
 *
 * Ported from magicui `animated-theme-toggler`. Two-state toggle:
 * dark ↔ light (system fallback is still honoured on fresh load via
 * ThemeProvider, but the toggle UI no longer exposes a system entry).
 *
 * Uses View Transitions API (`document.startViewTransition`) for the
 * circular reveal animation; falls back to instant swap if unsupported
 * or `prefers-reduced-motion` is set.
 *
 * Source motif: https://magicui.design/docs/components/animated-theme-toggler (MIT).
 */

import { Moon, Sun } from "lucide-react";
import { useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useTheme } from "../lib/theme-provider";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

type DocumentWithViewTransitions = Document & {
  startViewTransition?: (cb: () => void) => { ready: Promise<void> };
};

function _prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function ThemeToggle() {
  const { t } = useTranslation();
  const { resolved, setTheme } = useTheme();
  const buttonRef = useRef<HTMLButtonElement>(null);

  const isDark = resolved === "dark";
  const next = isDark ? "light" : "dark";
  const Icon = isDark ? Moon : Sun;
  const ariaLabel = isDark ? t("ui.themeToggle.toLight") : t("ui.themeToggle.toDark");

  const onToggle = useCallback(() => {
    const doc = document as DocumentWithViewTransitions;
    if (_prefersReducedMotion() || typeof doc.startViewTransition !== "function") {
      setTheme(next);
      return;
    }
    const rect = buttonRef.current?.getBoundingClientRect();
    const cx = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const cy = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
    const maxR = Math.hypot(
      Math.max(cx, window.innerWidth - cx),
      Math.max(cy, window.innerHeight - cy),
    );
    const transition = doc.startViewTransition(() => setTheme(next));
    void transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${cx}px ${cy}px)`, `circle(${maxR}px at ${cx}px ${cy}px)`] },
        { duration: 420, easing: "ease-in-out", pseudoElement: "::view-transition-new(root)" },
      );
    });
  }, [next, setTheme]);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          ref={buttonRef}
          type="button"
          data-testid="theme-toggle"
          data-theme-state={resolved}
          aria-label={ariaLabel}
          onClick={onToggle}
          className="inline-flex size-9 items-center justify-center rounded-(--radius-md) text-(--color-foreground) hover:bg-(--color-surface-2) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)"
        >
          <Icon className="size-4" />
          <span className="sr-only">{ariaLabel}</span>
        </button>
      </TooltipTrigger>
      <TooltipContent>{t("ui.themeToggle.label")}</TooltipContent>
    </Tooltip>
  );
}
