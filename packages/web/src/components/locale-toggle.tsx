import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";

const LOCALES = [
  { code: "zh-TW", label: "繁中" },
  { code: "en", label: "EN" },
] as const;

type LocaleCode = (typeof LOCALES)[number]["code"];

type LocaleToggleProps = {
  className?: string;
};

/**
 * Two-button segmented control for switching the app locale.
 *
 * Subscribes to i18n.language so re-renders happen automatically when
 * any other component (or the language detector) changes the locale.
 * Persistence to localStorage is handled by the i18next-browser-languagedetector
 * cache — no manual writes required here.
 */
export function LocaleToggle({ className }: LocaleToggleProps) {
  const { i18n } = useTranslation();
  const current = i18n.language as LocaleCode;

  return (
    <div
      className={cn(
        "inline-flex rounded-md border border-(--color-border) bg-(--color-card) p-0.5",
        className,
      )}
      role="group"
      aria-label="Language"
    >
      {LOCALES.map(({ code, label }) => {
        const isActive = current === code;
        return (
          <button
            key={code}
            type="button"
            onClick={() => {
              if (!isActive) i18n.changeLanguage(code);
            }}
            aria-pressed={isActive}
            className={cn(
              "rounded-[5px] px-2 py-0.5 text-xs font-medium transition-colors",
              isActive
                ? "bg-(--color-foreground) text-(--color-background)"
                : "text-(--color-muted-foreground) hover:text-(--color-foreground)",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
