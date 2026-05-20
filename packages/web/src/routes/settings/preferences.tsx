/**
 * /settings/preferences — slice-19 polish, Sean review round 2.
 *
 * Three equal-height cards: Language / Theme / Default ASR Provider.
 * The ASR provider card showcases real provider logos (Qwen + Whisper)
 * as selectable tiles — the selection itself is a no-op badge in
 * slice-19 (per design Decision 5 — "preferences sub-route 三個欄位只
 * 做 UI，不持久化").
 */

import { AudioLines, Languages, Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";
import { Badge } from "../../components/ui/badge";
import { useTheme, type Theme } from "../../lib/theme-provider";
import { cn } from "../../lib/utils";

interface AsrProvider {
  id: "qwen3";
  label: string;
  logo: React.ReactNode;
}

export function SettingsPreferences() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();

  // Post asr-runtime-extraction (ADR-0027): only Qwen3-ASR is offered.
  const providers: AsrProvider[] = [
    {
      id: "qwen3",
      label: "Qwen3-ASR",
      logo: <img src="/icons/qwen.png" alt="" aria-hidden className="size-7" />,
    },
  ];

  return (
    <div className="grid auto-rows-fr grid-cols-1 gap-4 md:grid-cols-3">
      {/* ─── Language card ──────────────────────────────────────────── */}
      <GradientCardFrame
        data-testid="settings-preferences-language-card"
        accent="var(--color-primary)"
        accentAlt="var(--color-accent)"
        className="h-full"
        bodyClassName="h-full"
      >
        <div className="flex h-full flex-col rounded-[inherit] p-6">
          <header className="flex items-center justify-center gap-2">
            <Languages className="size-4 text-(--color-primary)" aria-hidden />
            <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
              {t("settings.preferences.language_label")}
            </h2>
          </header>
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6">
            <div className="flex gap-2" role="radiogroup">
              {[
                { code: "zh-TW", label: "繁中" },
                { code: "en", label: "English" },
              ].map((opt) => {
                const active = i18n.language === opt.code;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    data-testid={`settings-preferences-language-${opt.code}`}
                    onClick={() => void i18n.changeLanguage(opt.code)}
                    className={cn(
                      "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                      active
                        ? "border-(--color-primary) bg-(--color-primary)/10 text-(--color-primary)"
                        : "border-(--color-border) text-(--color-muted-foreground) hover:bg-(--color-muted)",
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </GradientCardFrame>

      {/* ─── Theme card ─────────────────────────────────────────────── */}
      <GradientCardFrame
        data-testid="settings-preferences-theme-card"
        accent="var(--color-accent)"
        accentAlt="var(--color-primary)"
        className="h-full"
        bodyClassName="h-full"
      >
        <div className="flex h-full flex-col rounded-[inherit] p-6">
          <header className="flex items-center justify-center gap-2">
            <Sun className="size-4 text-(--color-accent)" aria-hidden />
            <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
              {t("settings.preferences.theme_label")}
            </h2>
          </header>
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6">
            <div className="flex gap-2" role="radiogroup">
              {(
                [
                  { val: "light" as Theme, icon: Sun, key: "light" },
                  { val: "dark" as Theme, icon: Moon, key: "dark" },
                  { val: "system" as Theme, icon: Monitor, key: "system" },
                ] as const
              ).map((opt) => {
                const Icon = opt.icon;
                const active = theme === opt.val;
                return (
                  <button
                    key={opt.val}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    data-testid={`settings-preferences-theme-${opt.val}`}
                    onClick={() => setTheme(opt.val)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-xs font-medium transition-colors",
                      active
                        ? "border-(--color-accent) bg-(--color-accent)/10 text-(--color-accent)"
                        : "border-(--color-border) text-(--color-muted-foreground) hover:bg-(--color-muted)",
                    )}
                  >
                    <Icon className="size-3.5" />
                    {t(`theme.toggle.${opt.key}`)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </GradientCardFrame>

      {/* ─── ASR provider card ─────────────────────────────────────── */}
      <GradientCardFrame
        data-testid="settings-preferences-asr-card"
        accent="var(--color-primary)"
        accentAlt="var(--color-accent)"
        className="h-full"
        bodyClassName="h-full"
      >
        <div className="flex h-full flex-col rounded-[inherit] p-6">
          <header className="flex items-center justify-center gap-2">
            <AudioLines className="size-4 text-(--color-primary)" aria-hidden />
            <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
              {t("settings.preferences.asr_label")}
            </h2>
            <Badge data-testid="settings-preferences-asr-coming-soon" variant="outline">
              {t("settings.preferences.coming_soon")}
            </Badge>
          </header>
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-6">
            <div className="grid grid-cols-2 gap-2">
              {providers.map((p) => {
                const active = p.id === "qwen3"; // slice-19: visual only, qwen3 = default
                return (
                  <div
                    key={p.id}
                    data-testid={`settings-preferences-asr-${p.id}`}
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-md border px-3 py-3 text-xs font-medium",
                      active
                        ? "border-(--color-primary) bg-(--color-primary)/10 text-(--color-foreground)"
                        : "border-(--color-border) bg-(--color-card) text-(--color-muted-foreground) opacity-70",
                    )}
                  >
                    {p.logo}
                    <span>{p.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </GradientCardFrame>
    </div>
  );
}
