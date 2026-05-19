/**
 * LocaleToggle — slice ui-overhaul-claude-design task 2.3.
 *
 * shadcn `DropdownMenu` trigger that shows the current locale code (`zh-TW`
 * / `EN`) and exposes the two options on click. Selecting an option calls
 * `i18n.changeLanguage(...)`. Active option marks with the `Check` icon to
 * mirror the ThemeToggle visual language.
 *
 * Persistence to localStorage is handled by the `i18next-browser-languagedetector`
 * cache — no manual writes here.
 */

import { Check, Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const LOCALES = [
  { code: "zh-TW", trigger: "zh-TW", label: "繁中" },
  { code: "en", trigger: "EN", label: "EN" },
] as const;

type LocaleCode = (typeof LOCALES)[number]["code"];

type LocaleToggleProps = {
  className?: string;
};

export function LocaleToggle({ className }: LocaleToggleProps) {
  const { i18n, t } = useTranslation();
  const current = i18n.language as LocaleCode;
  const activeLabel = LOCALES.find((l) => l.code === current)?.trigger ?? current;

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger
            type="button"
            data-testid="locale-toggle"
            aria-label={t("ui.tooltip.localeToggle")}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-(--color-foreground) hover:bg-(--color-muted) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)",
              className,
            )}
          >
            <Languages className="size-4 text-(--color-muted-foreground)" />
            <span>{activeLabel}</span>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>{t("ui.tooltip.localeToggle")}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="end" className="min-w-[8rem]">
        {LOCALES.map(({ code, label }) => {
          const isActive = current === code;
          return (
            <DropdownMenuItem
              key={code}
              data-testid={`locale-option-${code}`}
              data-active={isActive ? "true" : undefined}
              onSelect={() => {
                if (!isActive) i18n.changeLanguage(code);
              }}
              aria-pressed={isActive}
              className="flex items-center gap-2"
            >
              <span className="flex-1">{label}</span>
              {isActive ? <Check className="size-4 text-(--color-primary)" /> : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
