import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { LocaleToggle } from "./locale-toggle";
import { ThemeToggle } from "./theme-toggle";

type Props = {
  children: ReactNode;
  /** Optional small caption shown above the headline. */
  eyebrow?: string;
  /** Override the default app-name headline. Falls back to the i18n string. */
  headline?: string;
  /** Override the default subhead. Falls back to the i18n string. */
  subhead?: string;
};

/**
 * AuthShell — slice ui-overhaul-claude-design task 2.2.
 *
 * Centered scaffold shared by every auth-related route (login / signup /
 * TOTP). No NavBar; instead the top-right corner floats a small cluster
 * containing LocaleToggle + ThemeToggle so the user can pick language and
 * theme before authenticating. Children render centered in the viewport.
 */
export function AuthShell({ children, eyebrow, headline, subhead }: Props) {
  const { t } = useTranslation();
  const resolvedHeadline = headline ?? t("auth.shell.headline");
  const resolvedSubhead = subhead ?? t("auth.shell.subhead");

  return (
    <div
      data-testid="auth-shell"
      className="relative min-h-dvh overflow-hidden bg-(--color-background)"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[680px] -translate-x-1/2 rounded-full bg-(--color-primary)/10 blur-3xl"
      />
      <div
        data-testid="auth-shell-toolbar"
        className="absolute right-4 top-4 z-10 flex items-center gap-1"
      >
        <LocaleToggle />
        <ThemeToggle />
      </div>
      <main
        data-testid="auth-shell-main"
        className="relative mx-auto flex min-h-dvh max-w-md flex-col items-stretch justify-center gap-6 px-5 py-14"
      >
        <header className="space-y-2 text-center">
          {eyebrow && (
            <p className="text-xs uppercase tracking-[0.18em] text-(--color-muted-foreground)">
              {eyebrow}
            </p>
          )}
          <h1 className="text-2xl font-semibold tracking-tight text-(--color-foreground)">
            {resolvedHeadline}
          </h1>
          <p className="text-sm text-(--color-muted-foreground)">{resolvedSubhead}</p>
        </header>
        {children}
        <footer className="text-center text-xs text-(--color-muted-foreground)">
          {t("auth.shell.footer")}
        </footer>
      </main>
    </div>
  );
}
