/**
 * ThemeToggle — slice ui-overhaul-claude-design task 1.4.
 *
 * DropdownMenu trigger that cycles theme between light / dark / system.
 * Lives in the NavBar right-side cluster (ProtectedShell) and the floating
 * top-right corner of AuthShell. Uses lucide Sun / Moon / Monitor icons —
 * no emoji per project UI standards.
 */

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type Theme, useTheme } from "../lib/theme-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

const _options: { value: Theme; icon: typeof Sun; labelKey: string }[] = [
  { value: "light", icon: Sun, labelKey: "theme.toggle.light" },
  { value: "dark", icon: Moon, labelKey: "theme.toggle.dark" },
  { value: "system", icon: Monitor, labelKey: "theme.toggle.system" },
];

export function ThemeToggle() {
  const { t } = useTranslation();
  const { theme, resolved, setTheme } = useTheme();
  const TriggerIcon = resolved === "dark" ? Moon : Sun;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        type="button"
        data-testid="theme-toggle"
        title={t("theme.toggle.label")}
        className="inline-flex size-9 items-center justify-center rounded-md text-(--color-foreground) hover:bg-(--color-muted) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)"
      >
        <TriggerIcon className="size-4" />
        <span className="sr-only">{t("theme.toggle.label")}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[10rem]">
        {_options.map(({ value, icon: Icon, labelKey }) => {
          const active = theme === value;
          return (
            <DropdownMenuItem
              key={value}
              data-testid={`theme-option-${value}`}
              data-active={active ? "true" : undefined}
              onSelect={() => setTheme(value)}
              className="flex items-center gap-2"
            >
              <Icon className="size-4 text-(--color-muted-foreground)" />
              <span className="flex-1">{t(labelKey)}</span>
              {active ? <Check className="size-4 text-(--color-primary)" /> : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
